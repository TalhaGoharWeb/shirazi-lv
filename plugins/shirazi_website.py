"""One-command website builder — WebForge-lite (Shirazi LV plugin).

Learned from MYRA ULTRA's WebForge pipeline (MIT, (c) Vikas — see
docs/ATTRIBUTION.md): plan → generate → save → preview. This is the same
shape at Shirazi scale: the SMART text ladder (Gemini, then Groq, then
OpenRouter — the project's own failover) writes one complete, self-contained
HTML page from the spoken description; the page is saved under
Documents/Shirazi Websites/<name>/index.html and opened in the browser.

If no provider answers, a clean built-in template is generated instead, so
the user always gets a site — never an error in place of one. Deploying is
deliberately NOT automatic: publishing to GitHub/Vercel needs the user's own
tokens and their say-so, which a voice tool must not assume.
"""
from __future__ import annotations

import html as _html
import re
import webbrowser
from pathlib import Path

PLUGIN = {
    "name": "shirazi_website",
    "description": (
        "Builds a complete single-page website from a spoken description and opens it "
        "in the browser. Use for 'website bana do', 'ek site banao mere madrassa ke "
        "liye', 'make a landing page for my shop'. Pass the user's full description "
        "(business, style, sections, language) in 'description'; invent a short name "
        "if they didn't give one. The site is saved under Documents > Shirazi Websites. "
        "Say one short sentence first — generation takes a few seconds. This does NOT "
        "publish to the internet; it builds and previews locally."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "description": {
                "type": "STRING",
                "description": "What the site is for, its style/theme, sections wanted, "
                               "and language — everything known about the request.",
            },
            "name": {
                "type": "STRING",
                "description": "Short site/folder name, e.g. 'noor-madrassa'. Optional.",
            },
        },
        "required": ["description"],
    },
}

PLUGIN_SETTINGS = None

_MAX_HTML = 400_000  # a generated page beyond this is not a page, it's a leak


def _log(player, msg: str) -> None:
    if player:
        try:
            player.write_log(f"SHIRAZI: {msg}")
        except Exception:
            pass


def _slug(text: str, fallback: str = "my-website") -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", (text or "").lower()).strip("-")
    return (s[:40] or fallback)


def _prompt(description: str, name: str) -> str:
    return (
        "You are a world-class web developer. Build ONE complete, self-contained "
        "HTML page (all CSS and JS inline in the single file, no external assets "
        "except Google Fonts). Modern, polished, responsive design with a hero, "
        "clear sections, and a footer. Use the language of the description for "
        "the site's visible text. Output ONLY the HTML code — no explanations, "
        "no markdown fences.\n\n"
        f"Site name: {name}\n"
        f"What the user asked for: {description}"
    )


def _extract_html(text: str) -> str:
    """Pull a full HTML document out of a model reply, or return ''."""
    if not text:
        return ""
    t = text.strip()
    fence = re.search(r"```(?:html)?\s*(.*?)```", t, re.S | re.I)
    if fence:
        t = fence.group(1).strip()
    start = t.lower().find("<!doctype html")
    if start < 0:
        start = t.lower().find("<html")
    if start < 0:
        return ""
    end = t.lower().rfind("</html>")
    if end < 0:
        return ""
    page = t[start:end + len("</html>")]
    return page if len(page) <= _MAX_HTML else ""


def _fallback_html(description: str, name: str) -> str:
    title = _html.escape(name.replace("-", " ").title())
    desc = _html.escape(description)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  * {{ margin:0; padding:0; box-sizing:border-box; }}
  body {{ font-family: Georgia, 'Times New Roman', serif; background:#0b1220; color:#e8eef7; }}
  .hero {{ min-height:70vh; display:flex; flex-direction:column; align-items:center;
           justify-content:center; text-align:center; padding:3rem 1.5rem;
           background: radial-gradient(60rem 30rem at 50% -10%, #1d3a5f, #0b1220); }}
  h1 {{ font-size:clamp(2.2rem, 6vw, 4rem); letter-spacing:.02em; }}
  .tag {{ margin-top:1rem; max-width:42rem; color:#a9bdd6; font-size:1.15rem; line-height:1.6; }}
  .cta {{ margin-top:2rem; padding:.8rem 2rem; border:1px solid #57b6ff; color:#cfe9ff;
          border-radius:999px; text-decoration:none; }}
  section {{ max-width:60rem; margin:0 auto; padding:3rem 1.5rem; }}
  h2 {{ font-size:1.8rem; margin-bottom:1rem; color:#9fd0ff; }}
  p {{ line-height:1.7; color:#c4d2e4; }}
  footer {{ text-align:center; padding:2rem; color:#647d99; font-size:.9rem; }}
</style>
</head>
<body>
  <div class="hero">
    <h1>{title}</h1>
    <p class="tag">{desc}</p>
    <a class="cta" href="#about">Learn more</a>
  </div>
  <section id="about">
    <h2>About</h2>
    <p>{desc}</p>
    <p>This starter page was generated offline. Ask Shirazi to rebuild it while
       online for a fully designed version.</p>
  </section>
  <footer>Built with Shirazi LVI</footer>
</body>
</html>"""


def _generate(description: str, name: str) -> tuple[str, str]:
    """Returns (html, how) — 'how' names the source for the spoken reply."""
    try:
        from core.shirazi_ladder import text_with_fallback

        text = text_with_fallback(_prompt(description, name), tier="SMART",
                                  default="")
        page = _extract_html(text or "")
        if page:
            return page, "ai"
    except Exception:
        pass
    return _fallback_html(description, name), "template"


def run(parameters: dict, player=None, session_memory=None) -> str:
    """Mark-LV plugin contract: never raise; return a spoken string."""
    try:
        params = dict(parameters or {})
        description = str(params.get("description") or "").strip()
        if not description:
            return ("What kind of website should I build — what is it for, and "
                    "what style do you want?")
        name = _slug(str(params.get("name") or "") or description.split(".")[0])
        page, how = _generate(description, name)

        root = Path.home() / "Documents" / "Shirazi Websites" / name
        root.mkdir(parents=True, exist_ok=True)
        index = root / "index.html"
        n = 2
        base = root
        while index.exists():
            root = base.parent / f"{name}-{n}"
            root.mkdir(parents=True, exist_ok=True)
            index = root / "index.html"
            n += 1
        index.write_text(page, encoding="utf-8")
        try:
            webbrowser.open(index.as_uri())
        except Exception:
            pass
        _log(player, f"Website saved: {index} ({how})")
        if how == "ai":
            return (f"Website '{name}' is ready and open in your browser. "
                    f"It is saved in Documents, Shirazi Websites, {root.name}. "
                    "It is a local preview — say the word when you want it "
                    "published online.")
        return (f"Website '{name}' is ready and open in your browser, saved in "
                f"Documents, Shirazi Websites, {root.name}. No AI provider "
                "answered, so this is a clean starter template — ask me to "
                "rebuild it when you are online for the full design.")
    except Exception as e:
        return f"Website could not be built: {e}"
