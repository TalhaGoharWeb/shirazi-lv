"""QR code maker and reader (Shirazi LV plugin).

Gap filled from the MYRA ULTRA feature survey: Shirazi could only mint the
phone-dashboard pairing QR internally; the user had no QR tool. Now:
  * action='create' — any text / link becomes a QR PNG on the Desktop and is
    opened. Wi-Fi QRs are built from ssid+password ('wifi' action) so a guest
    can join by pointing a phone camera.
  * action='read' — decode a QR from an image file with OpenCV's detector
    (already a dependency for the camera), fully offline.
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

PLUGIN = {
    "name": "shirazi_qr",
    "description": (
        "Makes and reads QR codes. action='create' with text (a link, phone number, "
        "any text) saves a QR image to the Desktop and opens it. action='wifi' with "
        "ssid and password makes a join-my-Wi-Fi QR guests can scan. action='read' "
        "with image_path decodes the QR in that image file and reports its content. "
        "Use for 'QR bana do', 'is link ka QR code', 'wifi ka QR', 'ye QR scan karo'."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "action": {
                "type": "STRING",
                "enum": ["create", "wifi", "read"],
                "description": "create = QR from text; wifi = Wi-Fi join QR; read = decode an image.",
            },
            "text": {"type": "STRING", "description": "Content for action='create' (link, number, any text)."},
            "ssid": {"type": "STRING", "description": "Wi-Fi name for action='wifi'."},
            "password": {"type": "STRING", "description": "Wi-Fi password for action='wifi'."},
            "security": {
                "type": "STRING",
                "enum": ["WPA", "WEP", "nopass"],
                "description": "Wi-Fi security type; default WPA.",
            },
            "image_path": {"type": "STRING", "description": "Image file to decode for action='read'."},
        },
        "required": ["action"],
    },
}

PLUGIN_SETTINGS = None


def _log(player, msg: str) -> None:
    if player:
        try:
            player.write_log(f"SHIRAZI: {msg}")
        except Exception:
            pass


def _desktop() -> Path:
    d = Path.home() / "Desktop"
    return d if d.exists() else Path.home()


def _slug(text: str, fallback: str = "qr") -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text or "").strip("-").lower()
    return (s[:28] or fallback)


def _open_file(path: Path) -> None:
    try:
        if sys.platform.startswith("win"):
            os.startfile(str(path))  # noqa: S606
        elif sys.platform == "darwin":
            import subprocess

            subprocess.Popen(["open", str(path)])
        else:
            import subprocess

            subprocess.Popen(["xdg-open", str(path)])
    except Exception:
        pass


def _make_qr(payload: str, label: str, player) -> str:
    try:
        import qrcode
    except Exception:
        return "The qrcode package is not installed on this PC, so I cannot make QR codes."
    out = _desktop() / f"QR_{_slug(label)}.png"
    try:
        img = qrcode.make(payload)
        img.save(str(out))
    except Exception as e:
        return f"QR code could not be created: {e}"
    _open_file(out)
    _log(player, f"QR saved: {out}")
    return f"QR code saved to the Desktop as {out.name} and opened."


def _wifi_payload(ssid: str, password: str, security: str) -> str:
    def esc(v: str) -> str:
        return re.sub(r'([\\;,:"\[\]])', r"\\\1", v or "")

    sec = (security or "WPA").strip()
    if sec.lower() == "nopass":
        return f"WIFI:T:nopass;S:{esc(ssid)};;"
    return f"WIFI:T:{sec};S:{esc(ssid)};P:{esc(password)};;"


def _read_qr(image_path: str) -> str:
    p = Path(image_path or "").expanduser()
    if not p.is_file():
        return f"I cannot find an image at {image_path}."
    try:
        import cv2
    except Exception:
        return "OpenCV is not installed on this PC, so I cannot read QR codes."
    try:
        img = cv2.imread(str(p))
        if img is None:
            return f"That file could not be read as an image: {p.name}."
        det = cv2.QRCodeDetector()
        data, _pts, _ = det.detectAndDecode(img)
        texts = [data] if data else []
        if not texts:
            try:
                ok, infos, _pts2, _ = det.detectAndDecodeMulti(img)
                if ok:
                    texts = [t for t in infos if t]
            except Exception:
                pass
        if not texts:
            return f"No QR code found in {p.name}."
        if len(texts) == 1:
            return f"The QR code in {p.name} says: {texts[0]}"
        joined = " | ".join(texts)
        return f"Found {len(texts)} QR codes in {p.name}: {joined}"
    except Exception as e:
        return f"Reading the QR code failed: {e}"


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        action = str(params.get("action") or "").strip().lower()

        if action == "create":
            text = str(params.get("text") or "").strip()
            if not text:
                return "What should the QR code contain — a link, a number, or some text?"
            return _make_qr(text, text, player)
        if action == "wifi":
            ssid = str(params.get("ssid") or "").strip()
            password = str(params.get("password") or "")
            security = str(params.get("security") or "WPA").strip()
            if not ssid:
                return "What is the Wi-Fi name (SSID) for the QR code?"
            if security.lower() != "nopass" and not password:
                return f"What is the password for '{ssid}'? Say it and I will bake it into the QR."
            return _make_qr(_wifi_payload(ssid, password, security),
                            f"wifi-{ssid}", player)
        if action == "read":
            path = str(params.get("image_path") or "").strip()
            if not path:
                return "Which image file should I scan for a QR code? Give me its path."
            return _read_qr(path)
        return ("I can make a QR code from text or a link, make a Wi-Fi join QR, "
                "or read a QR from an image. Which one?")
    except Exception as e:
        return f"QR tool failed: {e}"
