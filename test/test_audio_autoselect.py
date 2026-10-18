"""auto_select(): picks the first device that genuinely moves audio."""
import sys, types
sys.path.insert(0, '.')

import core.audio_devices as ad


def _fake_sd(frames_per_open):
    """Fake sounddevice: device 0 delivers frames, device 1 delivers none,
    device 2 raises on open."""
    state = {"calls": 0}
    class FakeStream:
        def __init__(self, device=None, callback=None, **kw):
            self._dev = device
            self._cb = callback
            if device == 2:
                raise RuntimeError("nope")
        def start(self): state["calls"] += 1
        def stop(self): pass
        def close(self): pass
    fake = types.ModuleType("sounddevice")
    fake.InputStream = FakeStream
    fake.RawOutputStream = FakeStream
    fake.query_devices = lambda: []
    fake.query_hostapis = lambda: []
    return fake, state


def test_auto_select_input_skips_dead_endpoint(monkeypatch):
    fake_sd, _ = _fake_sd(None)
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    # list_devices -> ["mic-a", "mic-b"]; resolve maps name->index
    monkeypatch.setattr(ad, "list_devices", lambda kind: ["mic-a", "mic-b", "mic-c"])
    monkeypatch.setattr(ad, "resolve", lambda name, kind:
                        {"mic-a": 0, "mic-b": 1, "mic-c": 2}[name])
    # mic-a (idx 0): callback never fires in our fake (no frames) -> skip
    # To simulate frames, patch _frames_seen instead:
    monkeypatch.setattr(ad, "_frames_seen", lambda idx, probe_ms=700:
                        {0: 0, 1: 5, 2: 0}[idx])
    monkeypatch.setattr(ad, "_hardware_fingerprint", lambda kind: ("a", "b", "c"))
    ad._auto_cache.clear()
    assert ad.auto_select("input") == "mic-b"


def test_auto_select_caches(monkeypatch):
    calls = []
    monkeypatch.setattr(ad, "list_devices", lambda kind: calls.append(kind) or ["cached-mic"])
    monkeypatch.setattr(ad, "_hardware_fingerprint", lambda kind: ("cached-mic",))
    ad._auto_cache.clear()
    ad._auto_cache["input"] = ("cached-mic", ("cached-mic",))
    assert ad.auto_select("input") == "cached-mic"
    # list_devices called once for the membership check, no re-probe
    assert calls == ["input"]


def test_auto_select_reprobes_on_hardware_change(monkeypatch):
    monkeypatch.setattr(ad, "_hardware_fingerprint", lambda kind: ("mic-a", "mic-new"))
    monkeypatch.setattr(ad, "list_devices", lambda kind: ["mic-a", "mic-new"])
    monkeypatch.setattr(ad, "resolve", lambda name, kind: 0)
    monkeypatch.setattr(ad, "_frames_seen", lambda idx, probe_ms=700: 3)
    ad._auto_cache.clear()
    ad._auto_cache["input"] = ("mic-a", ("mic-a",))  # stale fingerprint
    assert ad.auto_select("input") == "mic-a"  # re-probed (fingerprint differed)
    assert ad._auto_cache["input"][1] == ("mic-a", "mic-new")


def test_auto_select_none_when_nothing_works(monkeypatch):
    monkeypatch.setattr(ad, "list_devices", lambda kind: ["mic-a"])
    monkeypatch.setattr(ad, "resolve", lambda name, kind: 0)
    monkeypatch.setattr(ad, "_frames_seen", lambda idx, probe_ms=700: 0)
    monkeypatch.setattr(ad, "_usable", lambda idx, kind: False)
    monkeypatch.setattr(ad, "_hardware_fingerprint", lambda kind: ("a",))
    ad._auto_cache.clear()
    assert ad.auto_select("input") is None
    assert ad.auto_select("output") is None
