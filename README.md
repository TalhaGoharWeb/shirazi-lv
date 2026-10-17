# SHIRAZI LV

**SHIRAZI** — a JARVIS-style desktop AI assistant for Windows. Pure Python (PyQt6 holographic HUD + Gemini Live voice), with the Shirazi assistant brain integrated: 58 tools, episodic memory, Urdu-first voice, a 3D Iron Man avatar, and a kids' storytelling mode.

> **Attribution:** SHIRAZI LV is built on **[Mark-LV](https://github.com/FatihMakes/mark-lv)** by **FatihMakes**, licensed **CC BY-NC 4.0**. Personal, non-commercial use with attribution — see [`docs/ATTRIBUTION.md`](docs/ATTRIBUTION.md) and [`LICENSE`](LICENSE). Not for sale or commercial use.

---

## ✨ What it does

| Area | Details |
|---|---|
| 🎙️ **Voice-first** | "Hey Shirazi" wake word (on-device), push-to-talk, full duplex voice via Gemini Live |
| 🖥️ **Holographic HUD** | PyQt6 interface with system monitors, activity log, command input, file upload |
| 🔵 **NoorCore** | Living-intelligence core visualizer — 8 states (Idle, Listening, Thinking, Speaking, Executing, Awaiting Approval, Error, Offline) driven by *real* events, audio-reactive ring from actual mic/playback levels |
| 🤖 **3D Iron Man** | Mark III helmet rendered live in Three.js — nods with your voice, eyes glow with speech, rim light shifts by state |
| 🧠 **Memory** | Episodic SQLite + full-text search memory — it remembers your conversations, facts, and preferences |
| 🛡️ **OmniControl** | Permission gateway: 4-tier risk model, voice + dashboard approvals, folder allow-lists, emergency stop, audit log |
| 🧩 **58 tools** | Notes, bookmarks, clipboard, timers, tasks, research, Excel, quizzes, problem diagnosis, GitHub (read-only), and more |
| 👶 **Bachon ki Dunya** | Kids mode — original moral stories (*sabaq-amoz kahaniyan*), Islamic lessons, and fun quizzes in simple Roman Urdu |
| 🌐 **Urdu-first** | Pin responses to Urdu / Roman Urdu; Urdu EdgeTTS voices |
| 📱 **Phone dashboard** | Futuristic remote-control dashboard over local Wi-Fi (QR pairing) |
| 🔑 **Provider failover** | Gemini → Groq → OpenRouter automatic failover for text tasks (all free tiers) |

---

## 🚀 Quick start (Windows)

**Requirements:** Windows 10/11 64-bit · Python 3.11+ · free [Gemini API key](https://aistudio.google.com/apikey) · internet

```bat
:: 1. Copy the shirazi-lv folder to your PC, open Command Prompt inside it
python setup.py        :: installs everything (takes a few minutes)

:: 2. Start SHIRAZI
python main.py
```

> **Lighter install:** `python setup.py --base` skips PyQt6-WebEngine (the 3D
> Iron Man avatar) — everything else works, and the HUD falls back to the
> NoorCore/Core visuals. Add 3D later with
> `pip install "PyQt6-WebEngine>=6.6,<7"`.

On first launch, open **⚙ Settings** and paste your Gemini API key (stored locally in `config/api_keys.json` — never uploaded anywhere). Optional: add free Groq / OpenRouter keys for automatic failover when Gemini quota runs out.

Full guide: [`docs/WINDOWS_SETUP.md`](docs/WINDOWS_SETUP.md)

---

## 🗣️ Talking to SHIRAZI

- *"Hey Shirazi"* (wake word) or click the mic — then just speak
- *"Bachon ko kahani sunao"* — a moral story for the kids
- *"Ahmed ko sabr ki kahani sunao"* — personalised storytelling
- *"Bachon ko duain sikhayo"* — Islamic lessons for children
- *"Note this down…"* / *"Remind me in 20 minutes…"* / *"Search the web for…"*
- HUD button cycles the centrepiece: **Animated Face → NoorCore → 3D Iron Man**

---

## 📁 Project structure

```
shirazi-lv/
├── main.py                 # entry point
├── setup.py                # one-shot Windows installer
├── ui.py                   # PyQt6 HUD (windows, overlays, dashboard QR)
├── core/
│   ├── noorcore.py         # Living Intelligence Core visualizer
│   ├── avatar3d.py         # 3D avatar bridge (QWebEngineView + Three.js)
│   ├── companion.py        # floating mini-core (opt-in)
│   ├── omnicontrol/        # permission gateway, policy, audit, orchestrator
│   ├── wake_word.py        # "Hey Shirazi" on-device wake word
│   ├── shirazi_ladder.py   # Gemini → Groq → OpenRouter failover
│   └── shirazi_language.py # Urdu / Roman Urdu pinning
├── plugins/                # 58 tools (drop a .py file to add one)
│   ├── _kids_content.py    # Bachon ki Dunya stories & lessons (original)
│   ├── shirazi_kids_story.py / shirazi_kids_lesson.py / shirazi_kids_quiz.py
│   └── shirazi_*.py        # notes, tasks, timers, research, excel, …
├── vendor/shirazi/         # vendored Shirazi assistant sources
├── ui/
│   ├── avatar3d.html       # Three.js scene (local r160, no CDN)
│   └── three/              # vendored Three.js
├── assets/avatar/ironman.glb  # Mark III helmet model
├── dashboard/              # phone remote-control web UI
├── memory/                 # episodic memory backend
├── docs/                   # guides (see below)
└── test/                   # test suite (pytest)
```

---

## 📚 Docs

| Guide | What |
|---|---|
| [`docs/WINDOWS_SETUP.md`](docs/WINDOWS_SETUP.md) | Install, keys, troubleshooting |
| [`docs/ATTRIBUTION.md`](docs/ATTRIBUTION.md) | License & credit for Mark-LV |
| [`docs/NOORCORE.md`](docs/NOORCORE.md) | Living Core states, themes, companion |
| [`docs/AVATAR3D.md`](docs/AVATAR3D.md) | 3D avatar — swapping the model |
| [`docs/OMNICONTROL.md`](docs/OMNICONTROL.md) | Permissions, risk tiers, emergency stop |
| [`docs/KIDS.md`](docs/KIDS.md) | Bachon ki Dunya — adding stories |
| [`docs/WAKEWORD_TRAINING.md`](docs/WAKEWORD_TRAINING.md) | Train "Hey Shirazi" on your voice |
| [`docs/INTEGRATION_MATRIX.md`](docs/INTEGRATION_MATRIX.md) | What came from Mark-LV vs Shirazi |

---

## 🧪 Tests

```bat
python -m pytest test/ -q
```

196 tests covering plugins, schemas, avatar, NoorCore, OmniControl, gateway authorization, task lifecycle, drafts, diagnostics, accessibility, and API-key handling.

---

## 🔒 Privacy

- API keys live only in `config/api_keys.json` on your PC (gitignored — never committed).
- Memory is a local SQLite database (`%USERPROFILE%\.shirazi\`).
- The wake word runs fully on-device; audio goes to Gemini Live only while you're talking to it.
- The phone dashboard uses a self-signed certificate on your local Wi-Fi only.

---

## 📜 License

- **This project:** built on Mark-LV © 2026 FatihMakes, **CC BY-NC 4.0** — you may use and adapt it personally with attribution; **commercial use is not permitted**. See [`LICENSE`](LICENSE).
- PyQt6 is GPL v3 (fine for personal use). Three.js is MIT (vendored).
- The Iron Man Mark III helmet model ships for personal use as the HUD avatar.

*SHIRAZI LV is a personal project — J.A.R.V.I.S. reimagined at home, in Urdu and English.* 🇵🇰
