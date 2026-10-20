"""Spotify control without a Spotify API account (Shirazi LV plugin).

Technique learned from MYRA ULTRA (MIT, (c) Vikas — see docs/ATTRIBUTION.md):
the official API needs a developer app and OAuth, but the desktop app already
answers to the `spotify:search:` URI scheme. So "play X" = open the search
URI, then (Windows) flip the screen-reader flag on for a moment so Spotify's
Chromium UI tree materialises, click the top result's Play button through UI
Automation, restore the flag, and VERIFY by reading the window title — the
title becomes "Artist – Song" only when something is actually playing. If it
cannot be verified, the tool says so instead of claiming success.

Transport (pause / next / previous) uses the OS media keys, which Spotify
honours from anywhere. Everything Windows-specific is guarded: on other
platforms the search still opens and the media keys still fire where the OS
supports them.
"""
from __future__ import annotations

import os
import sys
import time
import urllib.parse

PLUGIN = {
    "name": "shirazi_spotify",
    "description": (
        "Controls Spotify on this PC — no account setup needed. action='play' with a "
        "query ('atif aslam songs', 'lofi beats') searches Spotify and tries to start "
        "the top result, verifying playback from the window title. action='pause', "
        "'resume', 'next', 'previous' use the media keys. action='now_playing' reports "
        "what the Spotify window title shows. Use for ANY Spotify/music playback request "
        "('spotify pe lagao', 'gaana chalao spotify par', 'next song') — do NOT use "
        "youtube_video for Spotify requests, and do NOT just open the Spotify app with "
        "open_app when the user asked to PLAY something."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["play", "pause", "resume", "next", "previous", "now_playing"],
                "description": "What to do. 'play' needs query.",
            },
            "query": {
                "type": "STRING",
                "description": "Song / artist / playlist to search for (action='play' only). "
                               "Pass ONLY the search words, not the whole sentence.",
            },
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = None

_IS_WIN = sys.platform.startswith("win")


def _log(player, msg: str) -> None:
    if player:
        try:
            player.write_log(f"SHIRAZI: {msg}")
        except Exception:
            pass


def _spotify_title() -> str:
    """Current Spotify window title, or '' when not found / not Windows."""
    if not _IS_WIN:
        return ""
    try:
        import win32gui

        found = []

        def _cb(hwnd, _):
            try:
                t = win32gui.GetWindowText(hwnd)
                if t and ("Spotify" in t or " – " in t) and win32gui.IsWindowVisible(hwnd):
                    # The playing window's title is exactly the app name when idle,
                    # or "Artist – Track" while playing (no 'Spotify' in it then).
                    if t.startswith("Spotify") or " – " in t:
                        found.append(t)
            except Exception:
                pass

        win32gui.EnumWindows(_cb, None)
        # Prefer a track title over the bare app title.
        for t in found:
            if " – " in t:
                return t
        return found[0] if found else ""
    except Exception:
        return ""


def _media_key(key: str) -> bool:
    try:
        import pyautogui

        pyautogui.press(key)
        return True
    except Exception:
        return False


def _set_screen_reader(on: bool) -> None:
    """Flip SPI_SETSCREENREADER so Spotify builds its UIA tree (Windows only).

    Spotify is a Chromium app: with no screen reader present it never
    materialises its accessibility tree, and UI Automation sees an empty
    window. MYRA ULTRA's trick is to claim a screen reader exists, click,
    then put the flag back exactly as it was.
    """
    try:
        import ctypes

        SPI_SETSCREENREADER = 0x0047
        SPIF = 0x01 | 0x02  # UPDATEINIFILE | SENDCHANGE
        ctypes.windll.user32.SystemParametersInfoW(
            SPI_SETSCREENREADER, bool(on), None, SPIF)
    except Exception:
        pass


def _screen_reader_is_on() -> bool:
    try:
        import ctypes

        val = ctypes.c_bool(False)
        ctypes.windll.user32.SystemParametersInfoW(
            0x0046, 0, ctypes.byref(val), 0)  # SPI_GETSCREENREADER
        return bool(val.value)
    except Exception:
        return False


def _click_top_result_play() -> bool:
    """Best-effort: click the first result's Play button in the Spotify window."""
    try:
        from pywinauto import Desktop

        was_on = _screen_reader_is_on()
        _set_screen_reader(True)
        try:
            time.sleep(0.7)  # let the UIA tree materialise
            desk = Desktop(backend="uia")
            win = None
            for w in desk.windows():
                try:
                    if "spotify" in (w.window_text() or "").lower():
                        win = w
                        break
                except Exception:
                    continue
            if win is None:
                return False
            try:
                win.set_focus()
            except Exception:
                pass
            rect = win.rectangle()
            height = max(1, rect.bottom - rect.top)
            buttons = []
            for el in win.descendants(control_type="Button"):
                try:
                    name = (el.window_text() or "").strip().lower()
                    if name.startswith("play"):
                        r = el.rectangle()
                        buttons.append((r.top, el))
                except Exception:
                    continue
            if not buttons:
                return False
            buttons.sort(key=lambda b: b[0])
            # The top-most Play button below the header is the first result.
            for top, el in buttons:
                if top - rect.top > height * 0.12:
                    el.click_input()
                    return True
            buttons[0][1].click_input()
            return True
        finally:
            if not was_on:
                _set_screen_reader(False)
    except Exception:
        return False


def _open_search(query: str) -> bool:
    uri = "spotify:search:" + urllib.parse.quote(query)
    try:
        if _IS_WIN:
            os.startfile(uri)  # noqa: S606 - URI scheme handler, not a shell
            return True
        import subprocess

        opener = "open" if sys.platform == "darwin" else "xdg-open"
        subprocess.Popen([opener, uri])
        return True
    except Exception:
        return False


def _play(query: str, player) -> str:
    if not _open_search(query):
        return (f"Spotify search for '{query}' could not be opened on this PC. "
                "Is Spotify installed?")
    before = _spotify_title()
    clicked = False
    if _IS_WIN:
        time.sleep(2.2)  # search results need a moment to render
        clicked = _click_top_result_play()
        if clicked:
            time.sleep(1.2)
    after = _spotify_title()
    if after and " – " in after and after != before:
        _log(player, f"Spotify now playing: {after}")
        return f"Playing on Spotify: {after}."
    if clicked:
        return (f"Opened Spotify search for '{query}' and pressed play on the top "
                "result, but I could not verify playback from the window title — "
                "it may still be loading.")
    return (f"Opened Spotify with search results for '{query}'. "
            "Press play on the top result — I could not click it automatically.")


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        action = str(params.get("action") or "").strip().lower()
        query = str(params.get("query") or "").strip()

        if action == "play":
            if not query:
                return "Which song or artist should I play on Spotify?"
            return _play(query, player)
        if action in ("pause", "resume"):
            ok = _media_key("playpause")
            return ("Paused Spotify." if action == "pause" else "Resumed Spotify.") \
                if ok else "The media key could not be sent on this PC."
        if action == "next":
            return "Skipped to the next track." if _media_key("nexttrack") \
                else "The media key could not be sent on this PC."
        if action == "previous":
            return "Back to the previous track." if _media_key("prevtrack") \
                else "The media key could not be sent on this PC."
        if action == "now_playing":
            title = _spotify_title()
            if title and " – " in title:
                return f"Spotify is playing: {title}."
            if title:
                return "Spotify is open but nothing is playing right now."
            return "Spotify does not appear to be running."
        return ("Tell me what to do on Spotify — play a song, pause, resume, "
                "next, previous, or ask what is playing.")
    except Exception as e:
        return f"Spotify control failed: {e}"
