# SHIRAZI LVI — Windows Setup Guide

SHIRAZI LVI is a pure-Python desktop assistant (PyQt6 HUD + Gemini Live voice).
No Electron, no packaging, no build step — it runs directly from source.

## Requirements

- **Windows 10/11**, 64-bit
- **Python 3.11+** (you have 3.14 — supported; the installer warns above 3.13
  but does not block)
- A **Gemini API key** (free tier works): https://aistudio.google.com/apikey
- Internet connection (for the AI providers and first-time downloads)

## Install (one time)

1. Copy the `shirazi-lv` folder to your PC (e.g. `C:\shirazi-lv`).
2. Open **Command Prompt** in that folder and run:

```bat
python setup.py
```

This installs all Python dependencies and the Playwright browsers used for
web automation. It takes several minutes.


3. Start SHIRAZI:

```bat
python main.py
```

4. On first launch, open **⚙ Settings** and paste your **Gemini API key**.
   (Stored locally in `config/api_keys.json` — never uploaded anywhere.)

That's it. The holographic HUD appears; click the mic or press push-to-talk.

## Optional but recommended

| Feature | How |
|---|---|
| Provider failover (Groq/OpenRouter) | Settings → paste Groq / OpenRouter keys. When Gemini quota runs out, one-shot AI calls fail over automatically instead of dying. |
| "Hey Shirazi" wake word | ⚙ → WAKE WORD → one-click install (downloads the voice model). See `docs/WAKEWORD_TRAINING.md` to train it on *your* voice. |
| Urdu responses | Set `response_language` to `urdu` or `roman_urdu` (Settings, or in `config/api_keys.json`). The assistant then always replies in Urdu/Roman Urdu, and one-shot speech uses an Urdu voice. |
| Phone dashboard | The dashboard module from Mark-LV is included; pair from the HUD. |

## What lives where (on your PC)

- `config/api_keys.json` — API keys + settings. **Never share this file.**
- `%USERPROFILE%\.shirazi\` — episodic memory (SQLite), plugin data, your
  trained wake-word model (`wake_models\hey_shirazi.onnx`).
- `memory\long_term.json` — profile memory (facts about you).

## Troubleshooting

- **"No module named ..."** → re-run `python setup.py` (or
  `pip install -r requirements.txt`).
- **Mic not working** → ⚙ → audio devices; pick your input/output explicitly.
- **Gemini quota errors** → add a Groq key (free) for automatic failover.
- **Wake word not triggering** → it's opt-in; enable in ⚙ → WAKE WORD first.
- **Antivirus flags** → it's an unsigned local Python app; allow the folder.

## License note

Built on Mark-LV by FatihMakes (**CC BY-NC 4.0** — personal, non-commercial
use with attribution; see `docs/ATTRIBUTION.md`). Not for sale or commercial
use.
