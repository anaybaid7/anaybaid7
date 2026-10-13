"""Draws the "Lately" panel from live GitHub data.

    GITHUB_TOKEN=... python tools/live.py   # fetch fresh data, then draw
    python tools/live.py                    # redraw from data/live.json

The Action in .github/workflows/live.yml runs this every 6 hours. If the API
call fails, the last good data is reused so the panel never breaks.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import urllib.request
from pathlib import Path

from build import ACCENT, DISPLAY, MONO, OUT, REG, SEMI, THEMES, Doc, wrap, draw_rich, width

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "live.json"
USER = os.environ.get("PROFILE_USER", "anaybaid7")
SKIP = {USER}  # the profile repo itself would always be the latest push
WEEKS = 26

QUERY = """query($login: String!) { user(login: $login) {
  contributionsCollection { contributionCalendar { totalContributions
    weeks { contributionDays { contributionCount date } } } }
  repositories(first: 12, privacy: PUBLIC, ownerAffiliations: OWNER, isFork: false,
               orderBy: {field: PUSHED_AT, direction: DESC}) {
    nodes { name description pushedAt primaryLanguage { name } } }
} }"""


def fetch() -> dict:
    req = urllib.request.Request(
        "https://api.github.com/graphql",
        data=json.dumps({"query": QUERY, "variables": {"login": USER}}).encode(),
        headers={"Authorization": f"bearer {os.environ['GITHUB_TOKEN']}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        body = json.load(r)
    if "errors" in body:
        raise RuntimeError(body["errors"])
    u = body["data"]["user"]
    cal = u["contributionsCollection"]["contributionCalendar"]
    days = [d for w in cal["weeks"] for d in w["contributionDays"]]
    repos = [
        {"name": n["name"], "desc": n["description"] or "", "pushed": n["pushedAt"],
         "lang": (n["primaryLanguage"] or {}).get("name", "")}
        for n in u["repositories"]["nodes"] if n["name"] not in SKIP
    ][:3]
    return {"fetched": dt.datetime.now(dt.timezone.utc).isoformat(), "total": cal["totalContributions"],
            "days": [[d["date"], d["contributionCount"]] for d in days][-WEEKS * 7:], "repos": repos}


def ago(iso: str, now: dt.datetime) -> str:
    s = (now - dt.datetime.fromisoformat(iso.replace("Z", "+00:00"))).total_seconds()
    for unit, sec in (("month", 2592000), ("week", 604800), ("day", 86400), ("hour", 3600)):
        n = int(s // sec)
        if n >= 1:
            return f"pushed {n} {unit}{'' if n == 1 else 's'} ago"
    return "pushed just now"


def heat(doc: Doc, data: dict, x0: float, y0: float, cell: float, gap: float):
    days = data["days"]
    peak = max([c for _, c in days] + [1])
    teal = ACCENT["teal"]
    for i, (_, count) in enumerate(days):
        col, row = divmod(i, 7)
        x, y = x0 + col * (cell + gap), y0 + row * (cell + gap)
        if count == 0:
            doc.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" fill="{doc.t["line"]}"/>')
        else:
            op = 0.3 + 0.7 * (count / peak) ** 0.6
            doc.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell}" height="{cell}" rx="3" fill="{teal}" fill-opacity="{op:.2f}"/>')


def repo_rows(doc: Doc, data: dict, x: float, y: float, w: float, now: dt.datetime, title_size=20, body=14.5):
    colors = ["red", "amber", "sky"]
    for i, r in enumerate(data["repos"]):
        c = colors[i % 3]
        doc.raw(f'<circle cx="{x + 6}" cy="{y - 6}" r="5" fill="{doc.t["bg"]}" stroke="{ACCENT[c]}" stroke-width="3"/>')
        doc.text(x + 22, y, r["name"], DISPLAY, title_size, doc.t["ink"])
        meta = ago(r["pushed"], now) + (f", {r['lang']}" if r["lang"] else "")
        doc.text(x + 22, y + 21, meta, SEMI, 13, doc.t["text"][c])
        yy = y + 42
        for ln in wrap(r["desc"], w - 22, body)[:2]:
            draw_rich(doc, x + 22, yy, ln, body, doc.t["muted"], doc.t["ink"])
            yy += 21
        y = yy + 18
    return y


def panel(theme: str, mobile: bool, data: dict) -> str:
    now = dt.datetime.fromisoformat(data["fetched"]) if data.get("fetched") else dt.datetime.now(dt.timezone.utc)
    label = "Lately on GitHub. " + "; ".join(f"{r['name']}, {r['desc']}" for r in data.get("repos", []))
    if not data.get("repos"):
        doc = Doc(480 if mobile else 900, 120, theme, "Lately on GitHub")
        doc.text(30, 60, "Lately", DISPLAY, 28, doc.t["ink"])
        doc.text(30, 88, "Syncing with GitHub, back in a few minutes", REG, 15, doc.t["muted"])
        return doc.render()
    total = f"{data['total']:,} contributions in the last year"
    if not mobile:
        cell, gap = 13, 4
        grid_w = WEEKS * (cell + gap) - gap
        W, pad = 900, 34
        rows_x, rows_w = pad, W - pad * 3 - grid_w
        probe = Doc(W, 10, theme, label)
        end = repo_rows(probe, data, rows_x, 0, rows_w, now)
        H = max(112 + end + 8, pad + 46 + 7 * (cell + gap) + 70)
        doc = Doc(W, H, theme, label)
        doc.raw(f'<path d="M{pad} 30 L{pad + 46} 30" stroke="{ACCENT["teal"]}" stroke-width="8" stroke-linecap="round"/>')
        doc.text(pad, 70, "Lately", DISPLAY, 28, doc.t["ink"])
        repo_rows(doc, data, rows_x, 112, rows_w, now)
        gx = W - pad - grid_w
        doc.text(gx, 70, "Last 6 months", SEMI, 14.5, doc.t["text"]["teal"])
        heat(doc, data, gx, 96, cell, gap)
        doc.text(gx, 96 + 7 * (cell + gap) + 26, total, REG, 14, doc.t["muted"])
        doc.raw(f'<line x1="{gx - pad / 2 - 6}" y1="{pad}" x2="{gx - pad / 2 - 6}" y2="{H - pad}" stroke="{doc.t["line"]}" stroke-width="1.5"/>')
    else:
        W, pad = 480, 30
        cell, gap = 11.5, 3.5
        probe = Doc(W, 10, theme, label)
        end = repo_rows(probe, data, pad, 0, W - pad * 2, now, 21, 16)
        grid_h = 7 * (cell + gap)
        H = 112 + end + 30 + grid_h + 56
        doc = Doc(W, H, theme, label)
        doc.raw(f'<path d="M{pad} 26 L{pad + 46} 26" stroke="{ACCENT["teal"]}" stroke-width="8" stroke-linecap="round"/>')
        doc.text(pad, 66, "Lately", DISPLAY, 28, doc.t["ink"])
        y = repo_rows(doc, data, pad, 108, W - pad * 2, now, 21, 16)
        doc.text(pad, y + 6, "Last 6 months", SEMI, 15, doc.t["text"]["teal"])
        heat(doc, data, pad, y + 26, cell, gap)
        doc.text(pad, y + 26 + grid_h + 26, total, REG, 15, doc.t["muted"])
    return doc.render()


def main() -> None:
    data = json.loads(DATA.read_text()) if DATA.exists() else {}
    if os.environ.get("GITHUB_TOKEN"):
        try:
            data = fetch()
            DATA.parent.mkdir(exist_ok=True)
            DATA.write_text(json.dumps(data, indent=1) + "\n")
        except Exception as e:  # keep the last good panel rather than a broken one
            print("fetch failed, reusing cached data:", e)
    OUT.mkdir(exist_ok=True)
    for theme in THEMES:
        for mobile in (False, True):
            (OUT / f"live{'-m' if mobile else ''}-{theme}.svg").write_text(panel(theme, mobile, data))


if __name__ == "__main__":
    main()
