"""Script normalization for Urdu/Arabic-script memory text.

Applied at write time AND at query time so recall is script-variant tolerant.
Deterministic, pure function, stdlib only.

Normalization folds:
  - tashkeel (diacritics) U+064B..U+0652, U+0670
  - alef variants:  أ إ آ ٱ  ->  ا
  - yeh variants:   ي -> ی  (Farsi yeh),  ے -> ی
  - kaf:            ك -> ک  (Farsi kaf)
  - heh variants:   ة (teh marbuta) -> ہ,  ه -> ہ,  ھ -> ہ
  - noon-ghunna:    ں -> ن
  - Arabic-Indic digits ٠-٩ and Extended Arabic-Indic (Persian) ۰-۹ -> 0-9
"""

import re

_TASHKEEL = re.compile(r"[\u064B-\u0652\u0670]")
_ALEF = re.compile(r"[أإآٱ]")
_YEH = re.compile(r"[يے]")  # Arabic yeh + bari yeh -> Farsi yeh
_HEH = re.compile(r"[ۃهھ]")

_DIGIT_MAP = {}
for _i in range(10):
    _DIGIT_MAP[0x0660 + _i] = str(_i)  # ٠-٩ (ordinals: translate needs int keys)
    _DIGIT_MAP[0x06F0 + _i] = str(_i)  # ۰-۹


def normalize(text):
    """Normalize Urdu/Arabic-script text for memory indexing.

    Args:
        text: any object; non-str input is coerced via str().

    Returns:
        str: normalized text (whitespace not collapsed — callers decide).
    """
    s = text if isinstance(text, str) else str(text)
    s = _TASHKEEL.sub("", s)
    s = _ALEF.sub("ا", s)
    s = _YEH.sub("ی", s)
    s = s.replace("ك", "ک")
    s = _HEH.sub("ہ", s)
    s = s.replace("ں", "ن")
    if _DIGIT_MAP:
        s = s.translate(_DIGIT_MAP)
    return s
