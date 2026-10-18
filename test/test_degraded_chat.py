"""Phase 3.1 regression tests: degraded-mode text chat.

Covers: availability check, multi-turn history, history trimming,
prompt includes honest limits, ask() returns (answer, label).
"""
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.degraded_chat import DegradedChat, SYSTEM_PROMPT


@pytest.fixture
def chat():
    return DegradedChat()


class TestAvailability:
    def test_unavailable_without_keys(self, chat):
        with mock.patch("core.shirazi_ladder._key_for", return_value=""):
            assert chat.is_available() is False

    def test_available_with_groq_key(self, chat):
        def _kf(p):
            return "gsk_x" if p == "groq" else ""
        with mock.patch("core.shirazi_ladder._key_for", side_effect=_kf):
            assert chat.is_available() is True


class TestHistory:
    def test_ask_appends_both_turns(self, chat):
        with mock.patch("core.shirazi_ladder.oai_fallback_text",
                         return_value="hi there"), \
             mock.patch("core.shirazi_ladder.last_provenance",
                        return_value={"provider": "groq", "model": "m"}):
            ans, label = chat.ask("hello")
        assert ans == "hi there"
        assert label == "groq/m"
        h = chat.history()
        assert len(h) == 2
        assert h[0] == {"role": "user", "content": "hello"}
        assert h[1]["role"] == "assistant"

    def test_history_trims_to_max(self, chat):
        with mock.patch("core.shirazi_ladder.oai_fallback_text",
                         return_value="a"), \
             mock.patch("core.shirazi_ladder.last_provenance",
                        return_value={}):
            for i in range(30):
                chat.ask(f"q{i}")
        # 20 exchanges max = 40 messages
        assert len(chat.history()) == 40

    def test_prompt_states_honest_limits(self, chat):
        assert "TEXT-ONLY DEGRADED MODE" in SYSTEM_PROMPT
        assert "CANNOT use tools" in SYSTEM_PROMPT

    def test_prompt_includes_history(self, chat):
        with mock.patch("core.shirazi_ladder.oai_fallback_text",
                         return_value="a"), \
             mock.patch("core.shirazi_ladder.last_provenance",
                        return_value={}):
            chat.ask("first question")
        prompt = chat._build_prompt("second question")
        assert "first question" in prompt
        assert "second question" in prompt

    def test_clear(self, chat):
        with mock.patch("core.shirazi_ladder.oai_fallback_text",
                         return_value="a"), \
             mock.patch("core.shirazi_ladder.last_provenance",
                        return_value={}):
            chat.ask("hi")
        chat.clear()
        assert chat.history() == []

    def test_activate_deactivate(self, chat):
        assert chat.active is False
        chat.activate()
        assert chat.active is True
        chat.deactivate()
        assert chat.active is False
