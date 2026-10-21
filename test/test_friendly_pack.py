"""Tests for the friendly conversation pack (2026-10-21).

Covers the pure logic in core/conversation.py (barge-in voting, the
TOOL_STARTING watchdog, the tag's message format), the barge_in config
flag, the prompt's new conversation rules, and main.py's wiring seams.
"""
import asyncio
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from core.conversation import (  # noqa: E402
    BargeInVoter, ToolStartingWatchdog, tool_starting_message)


# ── BargeInVoter ─────────────────────────────────────────────────────

def test_voter_needs_consecutive_blocks():
    v = BargeInVoter(lambda: 3)
    assert v.feed(True) is False
    assert v.feed(True) is False
    assert v.feed(False) is False   # a gap resets the run
    assert v.feed(True) is False
    assert v.feed(True) is False
    assert v.feed(True) is True    # third in a row: interrupt


def test_voter_fires_once_then_resets():
    v = BargeInVoter(lambda: 2)
    assert v.feed(True) is False
    assert v.feed(True) is True
    assert v.feed(True) is False   # votes were consumed by the firing
    v.reset()
    assert v.feed(True) is False


def test_voter_bad_required_falls_back():
    v = BargeInVoter(lambda: 1 / 0)
    assert v.feed(True) is False   # fallback need=3, no exception
    assert v.feed(True) is False
    assert v.feed(True) is True


# ── ToolStartingWatchdog ─────────────────────────────────────────────

def test_watchdog_fires_after_delay():
    sent = []

    async def main():
        wd = ToolStartingWatchdog(sent.append, delay=0.05)
        wd.start("web_search")
        await asyncio.sleep(0.15)
        wd.cancel()
        return wd

    wd = asyncio.run(main())
    assert wd.fired
    assert len(sent) == 1
    assert "[TOOL_STARTING]" in sent[0]
    assert "web_search" in sent[0]


def test_watchdog_silent_when_cancelled_in_time():
    sent = []

    async def main():
        wd = ToolStartingWatchdog(sent.append, delay=0.2)
        wd.start("web_search")
        await asyncio.sleep(0.03)
        wd.cancel()
        await asyncio.sleep(0.25)
        return wd

    wd = asyncio.run(main())
    assert not wd.fired
    assert sent == []


def test_tool_starting_message_contract():
    msg = tool_starting_message("spotify")
    assert msg.startswith("[TOOL_STARTING]")
    assert "one short sentence" in msg
    assert "Do not call any tool" in msg


# ── config flag ──────────────────────────────────────────────────────

def test_barge_in_flag_roundtrip(monkeypatch):
    import memory.config_manager as cm
    tmp = Path(tempfile.mkdtemp())
    monkeypatch.setattr(cm, "CONFIG_FILE", tmp / "api_keys.json")
    monkeypatch.setattr(cm, "CONFIG_DIR", tmp)
    assert cm.get_barge_in_enabled() is False    # opt-in: off by default
    cm.save_barge_in_enabled(True)
    assert cm.get_barge_in_enabled() is True


# ── prompt rules ─────────────────────────────────────────────────────

def test_prompt_has_conversation_rules():
    text = (ROOT / "core" / "prompt.txt").read_text(encoding="utf-8")
    assert "[CONVERSATION]" in text
    assert "You are not a command line" in text
    assert "Mirror the user's own mix" in text
    assert "materially different actions" in text     # repair carve-out
    # The hard no-mix rules that fought natural code-switching are gone.
    assert "Do not mix two languages in one reply" not in text
    assert "Never mix languages" not in text


# ── main.py wiring (source-level; the audio paths need real hardware) ──

def test_main_wires_the_pack():
    src = (ROOT / "main.py").read_text(encoding="utf-8")
    assert "ToolStartingWatchdog" in src
    assert "_say_tool_starting" in src
    assert "_barge_voter.feed" in src
    assert "get_barge_in_enabled" in src
    assert 'getattr(sc, "interrupted", False)' in src
