# -*- coding: utf-8 -*-
"""
Conversation feel — the small mechanisms that make talking to the assistant
feel like talking to someone, not operating a machine.

Two pieces live here, both pure logic so they can be tested without audio
hardware or a live session:

1. **ToolStartingWatchdog** — the prompt has always documented a
   [TOOL_STARTING] tag ("a tool you just called is running now — say one
   short sentence"), but nothing ever sent it: the model announced quick
   tools in its own turn and slow ones left a silence. This watchdog
   watches one tool call; if it is still running after FILLER_DELAY, it
   asks the session to speak exactly one short sentence via the tag. The
   [ACKNOWLEDGE BEFORE A SILENCE] rule covers the start of the gap; this
   covers a gap that opens mid-tool.

2. **BargeInVoter** — voice barge-in (cutting the assistant off by
   speaking) needs several consecutive audio blocks that the EchoGuard
   believes are the user, not one loud block: a cough is one block, a
   person starting to talk is a run of them. The voter counts the run.
   Wired in main.py behind the `barge_in_enabled` config flag (default
   off — whether it behaves depends on the room and the speakers, so the
   user opts in and tries it on their own hardware).
"""
from __future__ import annotations

import asyncio

FILLER_DELAY = 2.5   # seconds of tool silence before a spoken filler is due


def tool_starting_message(tool_name: str) -> str:
    """The [TOOL_STARTING] client-content text for one running tool.

    Matches the contract in core/prompt.txt: the model says ONE short
    sentence, in the user's language, in its own words — and nothing else.
    """
    return (f'[TOOL_STARTING] The tool "{tool_name}" is still running. '
            "Say one short sentence in the user's language, in your own "
            "words, naming what you are doing right now — nothing else. "
            "Do not call any tool.")


class ToolStartingWatchdog:
    """Fire `send(text)` once if the watched work outlives the delay.

    `send` is a plain callable taking the message text; main.py passes one
    that injects the tagged turn into the Live session. Everything here is
    best-effort: a failed send is swallowed, because a filler is a courtesy,
    never a reason to disturb the tool call it watches.
    """

    def __init__(self, send, delay: float = FILLER_DELAY):
        self._send = send
        self._delay = delay
        self._task: asyncio.Task | None = None
        self.fired = False

    def start(self, tool_name: str) -> None:
        self.cancel()
        try:
            self._task = asyncio.ensure_future(self._run(tool_name))
        except RuntimeError:
            self._task = None   # no running loop — no filler, no harm

    async def _run(self, tool_name: str) -> None:
        await asyncio.sleep(self._delay)
        self.fired = True
        try:
            self._send(tool_starting_message(tool_name))
        except Exception:
            pass

    def cancel(self) -> None:
        if self._task is not None:
            self._task.cancel()
            self._task = None


class BargeInVoter:
    """Counts consecutive user-speech blocks; fires once per interruption.

    `required` is a callable returning how many consecutive blocks an
    interruption needs right now (EchoGuard.required_blocks — it adapts
    to how confident the guard is in its calibration).
    """

    def __init__(self, required):
        self._required = required
        self._votes = 0

    def reset(self) -> None:
        self._votes = 0

    def feed(self, is_user_speech: bool) -> bool:
        """True exactly once: on the block that completes the run."""
        if not is_user_speech:
            self._votes = 0
            return False
        self._votes += 1
        try:
            need = max(1, int(self._required()))
        except Exception:
            need = 3
        if self._votes >= need:
            self._votes = 0
            return True
        return False
