# Attribution & License — Shirazi LVI

Shirazi LVI is an integration project built on several codebases. License
notices for all of them are preserved below. Nothing here grants rights
beyond what each license allows.

## 1. Mark LV (foundation)

- Upstream: https://github.com/FatihMakes/Mark-LV
- Copyright (c) 2026 FatihMakes
- License: **Creative Commons Attribution-NonCommercial 4.0 International
  (CC BY-NC 4.0)** — see `LICENSE` (preserved verbatim from upstream).
- Canonical license text: https://creativecommons.org/licenses/by-nc/4.0/legalcode

What this means in practice:

- ✅ You may use, copy, and adapt this code for **personal, non-commercial**
  purposes (e.g. your own desktop assistant), **with attribution** to
  FatihMakes.
- ❌ **Commercial use is not permitted** — you may not sell it, monetize it,
  or use it in a commercial service without the author's permission.
- Adaptations must carry attribution and should note the changes made.

## 2. Mark LVI (engine upgrade — the "LVI wave")

- Upstream: https://github.com/FatihMakes/Mark-LVI
- Copyright (c) 2026 FatihMakes
- License: **CC BY-NC 4.0** (same terms as §1).

Ported from Mark LVI into this project:

- `providers/` — the pluggable provider engine: bring-your-own STT
  (Whisper), LLM (any OpenAI-compatible endpoint: Ollama, LM Studio,
  llama.cpp, vLLM, OpenAI, Groq, DeepSeek, Mistral, xAI, OpenRouter,
  Together) and TTS (Piper, system voices, ElevenLabs), with its own
  self-test suite (`providers/_tests.py`).
- `core/outcome.py` — outcome honesty: tools answer `done` (verified),
  `unverified` (sent, could not be confirmed) or `failed`, plus the
  `untrusted()` boundary wrapper for external content. Wired into the
  app open/close actions.

## 3. MYRA ULTRA (learned capabilities)

- Upstream: https://github.com/codeninjavik/myra-ultra
- Copyright (c) 2026 Vikas
- License: **MIT** (full text below).

Techniques learned from MYRA ULTRA and re-implemented in this project's
own plugin style (no MYRA code runs here verbatim; the plugins are new
code written for Shirazi's plugin contract):

- `plugins/shirazi_spotify.py` — Spotify control without an API account:
  `spotify:search:` URI + screen-reader-flag UI Automation click +
  window-title verification (MYRA's approach).
- `plugins/shirazi_website.py` — WebForge-style pipeline in miniature:
  spoken description → generated single-page site → local preview.
- `plugins/shirazi_qr.py`, `plugins/shirazi_ppt_create.py`,
  `plugins/shirazi_expense.py`, `plugins/shirazi_duplicates.py` —
  QR maker/reader, PowerPoint creation, expense log and duplicate
  finder, modelled on MYRA's tool catalog and quick-features layer.
- `core/prompt.txt` — the vision anti-hallucination rule ("describe only
  what the current frame actually shows") follows MYRA's prompt layer.

Deliberately NOT taken: MYRA's Wi-Fi password reader and its
confirmation-free WhatsApp sending — both clash with this project's
OmniControl permission model.

MIT License

Copyright (c) 2026 Vikas

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## 4. Shirazi Personal Assistant (integrated capabilities)

- Upstream: https://github.com/TalhaGoharWeb/shirazi-personal-assistant
- Original code written for this project; no third-party code copied.
- Shirazi-originated modules integrated here are marked with
  `# Shirazi-origin:` headers noting their source file.

## 5. Third-party dependencies

Each dependency keeps its own license (see `requirements.txt`). Notable:

- PyQt6 — GPL v3 (or commercial). Personal use on your own PC is fine;
  distributing a PyQt6-based app has GPL obligations — check before sharing.
- Other packages are permissive (MIT/Apache/BSD) — see their PyPI pages.

**Rule of thumb:** personal use on your own machines = fine. Sharing,
publishing, or selling = check every license first.
