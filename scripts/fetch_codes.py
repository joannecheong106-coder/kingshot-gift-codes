import json
import os
import re
import sys
from datetime import datetime, timezone
from urllib.request import Request, urlopen

WEBHOOK = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
PING_ROLE_ID = os.environ.get("PING_ROLE_ID", "").strip()
STATE_PATH = "posted_codes.json"

SOURCES = [
    ("kingshot.net gift-codes", "https://kingshot.net/gift-codes"),
    ("eldorado codes", "https://www.eldorado.gg/blog/kingshot-redeem-code/"),
]

CODE_REGEX = re.compile(r"\b[A-Z0-9]{6,16}\b")

def http_get(url: str) -> str:
    req = Request(url, headers={"User-Agent": "Mozilla/5.0 (gift-code-announcer)"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="ignore")

def load_state() -> set[str]:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            return set(json.load(f).get("codes", []))
    except Exception:
        return set()

def save_state(codes: set[str]) -> None:
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump({"codes": sorted(codes)}, f, indent=2)

def extract_codes(text: str) -> set[str]:
    blacklist = {"DISCORD", "ANDROID", "REDEEM", "WEBSITE", "SETTINGS", "GIFT"}
    found = set(m.group(0) for m in CODE_REGEX.finditer(text.upper()))
    return {c for c in found if c not in blacklist}

def post(new_codes: list[str], sources_hit: list[str]) -> None:
    import json as _json
    if not WEBHOOK:
        raise RuntimeError("Missing DISCORD_WEBHOOK_URL")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    ping = f"<@&{PING_ROLE_ID}>\n" if PING_ROLE_ID else ""
    lines = "\n".join([f"• `{c}`" for c in new_codes])
    src = ", ".join(sources_hit) if sources_hit else "mixed sources"
    content = (
        f"{ping}🎁 **New Gift Codes Found** ({now})\n"
        f"{lines}\n\n"
        f"_Sources checked: {src}_\n"
        f"Redeem ASAP (codes can expire / hit limits)."
    )
    payload = _json.dumps({"content": content}).encode("utf-8")
    req = Request(WEBHOOK, data=payload, headers={"Content-Type": "application/json"}, method="POST")
    with urlopen(req, timeout=30) as resp:
        resp.read()

def main():
    state = load_state()
    per_source = {}
    for name, url in SOURCES:
        try:
            per_source[name] = extract_codes(http_get(url))
        except Exception as e:
            print(f"Fetch failed for {name}: {e}", file=sys.stderr)
            per_source[name] = set()

    all_codes = set().union(*per_source.values())
    new = sorted([c for c in all_codes if c not in state])

    if not new:
        print("No new codes found.")
        return

    sources_hit = [src for src, codes in per_source.items() if any(c in codes for c in new)]
    post(new, sources_hit)
    state.update(new)
    save_state(state)
    print(f"Posted {len(new)} new code(s).")

if __name__ == "__main__":
    main()
