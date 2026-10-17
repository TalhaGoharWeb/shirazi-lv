"""Etsy listing plugin — for the DottedCreatives digital shop.

Two jobs, kept separate on purpose:

1. CONSTRAINT VALIDATION (listing_create / listing_check). YOU write the
   listing copy — title, description, 13 tags — because good copy is
   judgement work. This checks Etsy's REAL constraints deterministically:
   title <= 140 characters, exactly 13 tags, each tag <= 20 characters.
   Pass/fail per rule, with the offending items named. A listing that fails
   here would be rejected or truncated by Etsy itself.

2. PRICE MATH (price_suggest). Deterministic fee math for a Pakistan seller
   of digital products: fee = 13% of price + $0.50 (6.5% transaction +
   6.5% payment processing + $0.20 listing + $0.30 processing), keep = price
   - fee. No guessing, no "about" — the same numbers every time. This is
   the pre-Payoneer figure; Payoneer's withdrawal/conversion cut comes
   after and varies by account.

Permissions used: none (pure computation, stdlib only).
"""

TITLE_MAX = 140
TAGS_REQUIRED = 13
TAG_MAX = 20

# Reference price points with verified keep-per-sale (pre-Payoneer).
REFERENCE_PRICES = (9.97, 12.97, 14.97, 19.97)


def _fee(price: float):
    """Return (fee, keep) for a Pakistan digital-goods sale."""
    fee = round(price * 0.13 + 0.50, 2)
    return fee, round(price - fee, 2)


def _check_title(title: str):
    problems = []
    t = str(title or "")
    if not t.strip():
        problems.append("title is empty")
    if len(t) > TITLE_MAX:
        problems.append(f"title is {len(t)} chars (max {TITLE_MAX})")
    return problems


def _check_tags(tags):
    problems = []
    if not isinstance(tags, list):
        return ["tags must be a list of 13 strings"]
    if len(tags) != TAGS_REQUIRED:
        problems.append(f"{len(tags)} tags given, Etsy needs exactly "
                        f"{TAGS_REQUIRED}")
    seen = set()
    for i, tag in enumerate(tags, 1):
        t = str(tag or "").strip()
        if not t:
            problems.append(f"tag {i} is empty")
            continue
        if len(t) > TAG_MAX:
            problems.append(f"tag {i} '{t[:30]}' is {len(t)} chars "
                            f"(max {TAG_MAX})")
        low = t.casefold()
        if low in seen:
            problems.append(f"tag {i} '{t}' is a duplicate")
        seen.add(low)
    return problems


def _report(title, tags):
    problems = _check_title(title) + _check_tags(tags or [])
    lines = []
    t = str(title or "")
    lines.append(f"Title: {len(t)}/{TITLE_MAX} chars — "
                 + ("PASS" if len(t) <= TITLE_MAX and t.strip() else "FAIL"))
    n = len(tags) if isinstance(tags, list) else 0
    lines.append(f"Tags: {n}/{TAGS_REQUIRED} — "
                 + ("PASS" if n == TAGS_REQUIRED else "FAIL"))
    bad = [str(tag) for tag in (tags or [])
           if len(str(tag).strip()) > TAG_MAX]
    lines.append(f"Tag length (each <= {TAG_MAX}): "
                 + ("PASS" if not bad else f"FAIL — {len(bad)} too long"))
    if problems:
        lines.append("")
        lines.append("Fix these:")
        lines.extend(f"  - {p}" for p in problems)
    else:
        lines.append("All Etsy constraints PASS — ready to list.")
    return "\n".join(lines)


def run_create(args):
    title = str(args.get("title") or "")
    description = str(args.get("description") or "").strip()
    tags = args.get("tags")
    if not title and not tags:
        return ("I need the listing copy — write the title, description and "
                "13 tags yourself (you know the product and the audience), "
                "then call listing_create again with them. I'll validate "
                "Etsy's constraints: title <= 140 chars, exactly 13 tags, "
                "each tag <= 20 chars.")
    out = [f"Product: {args.get('product_name', '')}", "", _report(title, tags)]
    if description:
        out += ["", f"Description ({len(description)} chars) — kept as you "
                "wrote it."]
    return "\n".join(out)


def run_check(args):
    return _report(str(args.get("title") or ""), args.get("tags"))


def run_price(args):
    try:
        price = float(args.get("price_usd", 0))
    except (TypeError, ValueError):
        return "Give me the price in USD, e.g. price_usd: 14.97."
    if price <= 0:
        return "The price has to be above zero."
    fee, keep = _fee(price)
    lines = [f"Price ${price:.2f}:",
             f"  Etsy fee (13% + $0.50): ${fee:.2f}",
             f"  You keep (pre-Payoneer): ${keep:.2f}",
             "",
             "Reference points (pre-Payoneer):"]
    for ref in REFERENCE_PRICES:
        f, k = _fee(ref)
        lines.append(f"  ${ref:.2f} -> fee ${f:.2f}, keep ${k:.2f}")
    lines += ["",
              "Note: Payoneer's withdrawal + conversion cut comes after "
              "this and varies by account. Offsite Ads is OFF by choice — "
              "a 15% attribution cut would gut these margins."]
    return "\n".join(lines)


TOOLS = [
    {"name": "listing_create",
     "description": (
         "Validates a full Etsy listing you wrote. YOU write the copy — a "
         "compelling title (<=140 chars), a description that sells the "
         "digital product, and EXACTLY 13 tags (each <=20 chars, no "
         "duplicates). Pass them in; this returns pass/fail per Etsy rule "
         "with the offenders named. Say one short sentence first while you "
         "compose ('Listing banata hoon...')."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "product_name": {"type": "string"},
             "details": {"type": "string",
                         "description": "What the product is, for your "
                                        "reference while writing."},
             "audience": {"type": "string",
                          "description": "Who it's for, e.g. 'ADHD adults', "
                                         "'Muslim planners'."},
             "title": {"type": "string",
                       "description": "The listing title you wrote (<=140)."},
             "description": {"type": "string",
                             "description": "The listing description."},
             "tags": {"type": "array", "items": {"type": "string"},
                      "description": "Exactly 13 tags, each <= 20 chars."}},
         "required": ["title", "tags"]},
     "run": run_create},
    {"name": "listing_check",
     "description": (
         "Quick Etsy constraint check on a title + tags you already have "
         "(e.g. re-checking after edits). Same rules as listing_create."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "title": {"type": "string"},
             "tags": {"type": "array", "items": {"type": "string"}}},
         "required": ["title", "tags"]},
     "run": run_check},
    {"name": "price_suggest",
     "description": (
         "Deterministic Etsy fee math for a Pakistan digital seller: fee = "
         "13% + $0.50, keep = price - fee. Shows the breakdown for your "
         "price plus the $9.97/$12.97/$14.97/$19.97 reference points. Use "
         "whenever pricing a product — never guess the fee."),
     "kind": "native", "access": "read",
     "parameters": {
         "type": "object",
         "properties": {
             "price_usd": {"type": "number",
                           "description": "Candidate price in USD."}},
         "required": ["price_usd"]},
     "run": run_price},
]
