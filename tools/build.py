"""Draws every image in assets/ in four variants: desktop and mobile, dark and light.

    python tools/build.py

README.md picks the right one with <picture> media queries, so a phone gets a
layout made for a phone and light-mode GitHub gets a light design. Fonts are
subset and embedded because GitHub shows README SVGs as plain <img> tags.
Text marked **like this** in the content below is drawn bold and bright.
"""
from __future__ import annotations

import base64
import io
import re
from pathlib import Path
from xml.sax.saxutils import escape

from fontTools.subset import Options, Subsetter
from fontTools.ttLib import TTFont

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "tools" / "fonts"
OUT = ROOT / "assets"
DISPLAY = FONTS / "bricolage-grotesque-latin-800-normal.woff2"
SEMI = FONTS / "instrument-sans-latin-600-normal.woff2"
REG = FONTS / "instrument-sans-latin-400-normal.woff2"
MONO = FONTS / "jetbrains-mono-latin-500-normal.woff2"

# ------------------------------------------------------------------ content
# All words live in content.yaml at the repo root.

import yaml  # noqa: E402

C = yaml.safe_load((ROOT / "content.yaml").read_text())
NAME = C["name"]
HERO_SUB = C["tagline"]
FACTS = [(f["label"], f["value"], f["color"]) for f in C["facts"]]
CAREER = [(c["company"], c["role"], c["win"], c["color"]) for c in C["career"]]
JOBS = C["jobs"]
PROJECTS = C["projects"]
EDUCATION = {**C["education"], "tags": []}
STACK = [(g["group"], g["color"], g["items"]) for g in C["stack"]]

SECTIONS = {"experience": ("Where I've been", "red"), "stack": ("Stack", "teal"),
            "projects": ("Things I've built", "amber"), "education": ("Education", "sky")}

BUTTONS = {"resume": ("Resume", "red"), "portfolio": ("Portfolio", "teal"), "linkedin": ("LinkedIn", "sky"), "email": ("Email", "amber")}

# ------------------------------------------------------------------ themes
# stroke colors are shared, text colors darken on light so they pass contrast

ACCENT = {"red": "#FF4B3E", "amber": "#FFB800", "teal": "#00C2A8", "sky": "#3DA9FC", "pink": "#E84FD0"}
THEMES = {
    "dark": dict(bg="#0E1A3D", ink="#F4F6FF", muted="#9AA6D6", line="#2A3A72", node="#F4F6FF", ring="#0E1A3D", rw=5,
                 text={"red": "#FF6B5F", "amber": "#FFB800", "teal": "#00C2A8", "sky": "#5AB8FF", "pink": "#F06ADB"}),
    "light": dict(bg="#F2F4FB", ink="#0E1A3D", muted="#4C5888", line="#D2D9EE", node="#FFFFFF", ring="#0E1A3D", rw=3.5,
                  text={"red": "#C8261A", "amber": "#8A5A00", "teal": "#007A66", "sky": "#1764B8", "pink": "#A82590"}),
}

# ------------------------------------------------------------------ fonts


def subset_b64(path: Path, chars: str) -> str:
    font = TTFont(path, recalcTimestamp=False)  # stable bytes, so CI only commits real changes
    opts = Options()
    opts.flavor = "woff2"
    opts.layout_features = ["kern", "liga"]
    s = Subsetter(opts)
    s.populate(text="".join(sorted(set(chars + " "))))
    s.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    return base64.b64encode(buf.getvalue()).decode()


_fonts: dict[Path, TTFont] = {}


def width(text: str, path: Path, size: float) -> float:
    font = _fonts.setdefault(path, TTFont(path))
    cmap, hmtx = font.getBestCmap(), font["hmtx"]
    return sum(hmtx[cmap.get(ord(c), cmap[32])][0] for c in text) * size / font["head"].unitsPerEm


class Doc:
    """Collects SVG pieces and the characters each font needs."""

    def __init__(self, w: float, h: float, theme: str, label: str):
        self.w, self.h, self.t, self.label = w, h, THEMES[theme], label
        self.parts: list[str] = []
        self.css: list[str] = []
        self.chars = {DISPLAY: "", SEMI: "", REG: "", MONO: ""}

    def text(self, x, y, s, font, size, fill, anchor="start", extra=""):
        cls = {DISPLAY: "d", SEMI: "s", REG: "r", MONO: "m"}[font]
        self.chars[font] += s
        self.parts.append(f'<text class="{cls}" x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{fill}" text-anchor="{anchor}" {extra}>{escape(s)}</text>')

    def raw(self, s: str):
        self.parts.append(s)

    def node(self, x, y, r=9, ring=None):
        self.raw(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="{self.t["node"]}" stroke="{ring or self.t["ring"]}" stroke-width="{self.t["rw"]}"/>')

    def render(self, panel=True, clip=True) -> str:
        faces = []
        for path, fam, cls, weight in ((DISPLAY, "D", "d", 800), (SEMI, "S", "s", 600), (REG, "R", "r", 400), (MONO, "M", "m", 500)):
            if self.chars[path]:
                faces.append(f"@font-face{{font-family:{fam};src:url(data:font/woff2;base64,{subset_b64(path, self.chars[path])}) format('woff2')}}")
        base = (".d{font-family:D,'Arial Black',sans-serif;font-weight:800}.s{font-family:S,Helvetica,Arial,sans-serif;font-weight:600}"
                ".r{font-family:R,Helvetica,Arial,sans-serif}.m{font-family:M,ui-monospace,Menlo,monospace}")
        w, h = round(self.w), round(self.h)
        head = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{escape(self.label)}">'
                f"<style>{''.join(faces)}{base}{''.join(self.css)}</style>")
        bg = ""
        if panel:
            bg = f'<defs><clipPath id="c"><rect width="{w}" height="{h}" rx="20"/></clipPath></defs><g clip-path="url(#c)"><rect width="{w}" height="{h}" fill="{self.t["bg"]}"/>'
        return head + bg + "".join(self.parts) + ("</g>" if panel else "") + "</svg>\n"


# ------------------------------------------------------------------ text layout


def rich_words(s: str) -> list[tuple[str, bool]]:
    words: list[tuple[str, bool]] = []
    parts = re.split(r"\*\*", s)
    for i, part in enumerate(parts):
        toks = part.split()
        if toks and words and not part[:1].isspace() and not parts[i - 1][-1:].isspace():
            prev, b = words.pop()
            words.append((prev + toks.pop(0), b))
        words += [(w, i % 2 == 1) for w in toks]
    return words


def wrap(s: str, max_w: float, size: float, plain_font=REG, bold_font=SEMI) -> list[list[tuple[str, bool]]]:
    lines, cur, cur_w = [], [], 0.0
    for w, b in rich_words(s):
        ww = width(w + " ", bold_font if b else plain_font, size)
        if cur and cur_w + ww > max_w:
            lines.append(cur)
            cur, cur_w = [], 0.0
        cur.append((w, b))
        cur_w += ww
    return lines + ([cur] if cur else [])


def draw_rich(doc: Doc, x, y, line, size, plain, bold):
    spans = []
    for w, b in line:
        f = SEMI if b else REG
        doc.chars[f] += w
        spans.append(f'<tspan class="{"s" if b else "r"}" fill="{bold if b else plain}">{escape(w)} </tspan>')
    doc.raw(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" xml:space="preserve">{"".join(spans)}</text>')


def pills(doc: Doc | None, x0, y, items, max_w, size=12, stroke=None, fill=None, font=MONO, h=26, gap=8):
    """Lays out pill tags with wrapping; returns the y below the last row."""
    x = x0
    for it in items:
        pw = width(it, font, size) + 22
        if x > x0 and x + pw > x0 + max_w:
            x, y = x0, y + h + gap
        if doc:
            doc.raw(f'<rect x="{x:.1f}" y="{y:.1f}" width="{pw:.1f}" height="{h}" rx="{h / 2}" fill="{fill or "none"}" stroke="{stroke}" stroke-width="1.5"/>')
            doc.text(x + 11, y + h / 2 + size * 0.36, it, font, size, doc.t["muted"] if not fill else doc.t["ink"])
        x += pw + gap
    return y + h


# ------------------------------------------------------------------ hero


def bez(p0, p1, p2, p3, t):
    u = 1 - t
    return tuple(u**3 * a + 3 * u * u * t * b + 3 * u * t * t * c + t**3 * d for a, b, c, d in zip(p0, p1, p2, p3))


def curve_bundle(doc: Doc, hub, x_in, x_out, ins, outs, sw=11, mid=140):
    colors = ["sky", "teal", "red", "amber", "pink"]
    light_path, nodes, paths = "", [], []
    for i, c in enumerate(colors):
        a = ((x_in, ins[i]), (hub[0] - mid, ins[i]), (hub[0] - mid, hub[1]), hub)
        b = (hub, (hub[0] + mid - 20, hub[1]), (hub[0] + mid - 20, outs[i]), (x_out, outs[i]))
        d = (f"M{a[0][0]} {a[0][1]} C{a[1][0]} {a[1][1]} {a[2][0]} {a[2][1]} {a[3][0]} {a[3][1]} "
             f"C{b[1][0]} {b[1][1]} {b[2][0]} {b[2][1]} {b[3][0]} {b[3][1]}")
        if c == "red":
            light_path = d
        paths.append(f'<path class="ln" style="animation-delay:{0.1 * i:.1f}s" d="{d}" pathLength="1" fill="none" '
                     f'stroke="{ACCENT[c]}" stroke-width="{sw}" stroke-linecap="round"/>')
        x, y = bez(*b, 0.62)
        nodes.append((x, y))
        nodes.append(a[0])
    doc.raw("".join(paths))
    doc.raw('<g class="nd">')
    for x, y in nodes:
        doc.node(x, y, 8)
    doc.raw(f'<circle cx="{hub[0]}" cy="{hub[1]}" r="22" fill="{doc.t["node"]}" stroke="{doc.t["ring"]}" stroke-width="{doc.t["rw"] + 1}"/>')
    doc.raw(f'<circle class="bt" cx="{hub[0]}" cy="{hub[1]}" r="22" fill="none" stroke="{doc.t["ink"]}" stroke-width="2"/></g>')
    glow = "#ffffff" if doc.t is THEMES["dark"] else ACCENT["red"]
    doc.raw('<defs><filter id="g" x="-200%" y="-200%" width="500%" height="500%"><feGaussianBlur stdDeviation="4" result="b"/>'
            '<feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter></defs>'
            f'<circle class="lt" r="6" fill="{glow}" filter="url(#g)"/>')
    doc.css.append(
        ".ln{stroke-dasharray:1;stroke-dashoffset:1;animation:dr 1.3s cubic-bezier(.6,0,.2,1) forwards}"
        ".nd{opacity:0;animation:pp .4s ease-out 1.2s forwards}"
        ".bt{transform-box:fill-box;transform-origin:center;opacity:0;animation:bt 3s ease-out 1.6s infinite}"
        f".lt{{offset-path:path('{light_path}');offset-distance:0%;opacity:0;animation:rn 4.5s cubic-bezier(.5,0,.3,1) 1.8s infinite}}"
        "@keyframes dr{to{stroke-dashoffset:0}}@keyframes pp{to{opacity:1}}"
        "@keyframes bt{0%{transform:scale(1);opacity:.7}100%{transform:scale(2.2);opacity:0}}"
        "@keyframes rn{0%{offset-distance:0%;opacity:0}8%{opacity:1}90%{opacity:1}100%{offset-distance:100%;opacity:0}}"
        "@media (prefers-reduced-motion:reduce){.ln{animation:none;stroke-dashoffset:0}.nd{animation:none;opacity:1}.bt,.lt{display:none}}"
    )


def hero(theme: str, mobile: bool) -> str:
    label = f"{NAME}. " + HERO_SUB
    if not mobile:
        doc = Doc(900, 400, theme, label)
        curve_bundle(doc, (705, 212), 445, 910, [70, 150, 232, 315, 378], [340, 50, 222, 385, 128])
        doc.text(44, 168, NAME.split()[0], DISPLAY, 132, doc.t["ink"], extra='letter-spacing="-4"')
        doc.text(44, 290, NAME.split()[-1], DISPLAY, 132, doc.t["ink"], extra='letter-spacing="-4"')
        for i, ln in enumerate(wrap(HERO_SUB, 400, 17)):
            draw_rich(doc, 48, 338 + i * 24, ln, 17, doc.t["muted"], doc.t["ink"])
    else:
        doc = Doc(480, 600, theme, label)
        doc.text(30, 130, NAME.split()[0], DISPLAY, 116, doc.t["ink"], extra='letter-spacing="-3"')
        doc.text(30, 236, NAME.split()[-1], DISPLAY, 116, doc.t["ink"], extra='letter-spacing="-3"')
        for i, ln in enumerate(wrap(HERO_SUB, 424, 18)):
            draw_rich(doc, 34, 282 + i * 26, ln, 18, doc.t["muted"], doc.t["ink"])
        curve_bundle(doc, (250, 470), -10, 490, [370, 420, 470, 520, 570], [560, 380, 470, 590, 420], sw=10, mid=120)
    return doc.render()


# ------------------------------------------------------------------ career


def career(theme: str, mobile: bool) -> str:
    label = "Career. " + ", ".join(f"{n}, {r}" for n, r, *_ in CAREER) + ". Open to new grad roles in 2027."
    if not mobile:
        W, H, Y = 900, 300, 150
        doc = Doc(W, H, theme, label)
        xs, end_x = [125, 260, 395, 530, 680], 820
        seg = [75] + xs
        for i, (*_, c) in enumerate(CAREER):
            doc.raw(f'<line x1="{seg[i]}" y1="{Y}" x2="{seg[i + 1]}" y2="{Y}" stroke="{ACCENT[c]}" stroke-width="12" stroke-linecap="round"/>')
        doc.raw(f'<line x1="{xs[-1]}" y1="{Y}" x2="{end_x}" y2="{Y}" stroke="{ACCENT["red"]}" stroke-width="12" stroke-linecap="round" stroke-dasharray="2 22"/>')
        for i, (name, role, metric, c) in enumerate(CAREER):
            x, up = xs[i], i % 2 == 0
            y0 = Y - 86 if up else Y + 50
            doc.node(x, Y, 14 if i == 4 else 11)
            doc.raw(f'<line x1="{x}" y1="{Y + (-18 if up else 18)}" x2="{x}" y2="{Y + (-28 if up else 28)}" stroke="{doc.t["muted"]}" stroke-width="2"/>')
            doc.text(x, y0, name, DISPLAY, 21, doc.t["ink"], "middle")
            doc.text(x, y0 + 21, role, REG, 13.5, doc.t["muted"], "middle")
            doc.text(x, y0 + 42, metric, SEMI, 14.5, doc.t["text"][c], "middle")
        here = (xs[-1], Y)
        doc.raw(f'<circle cx="{end_x}" cy="{Y}" r="12" fill="{doc.t["bg"]}" stroke="{doc.t["ink"]}" stroke-width="4" stroke-dasharray="5 4"/>')
        doc.text(end_x, Y + 60, "2027", DISPLAY, 21, doc.t["ink"], "middle")
        doc.text(end_x, Y + 81, "open to new grad", REG, 13.5, doc.t["muted"], "middle")
    else:
        step, top = 100, 56
        W, H = 480, top + step * 5 + 70
        doc = Doc(W, H, theme, label)
        X = 52
        ys = [top + i * step for i in range(6)]
        for i, (*_, c) in enumerate(CAREER):
            doc.raw(f'<line x1="{X}" y1="{ys[i]}" x2="{X}" y2="{ys[i + 1] if i < 4 else ys[i]}" stroke="{ACCENT[c]}" stroke-width="12" stroke-linecap="round"/>')
        doc.raw(f'<line x1="{X}" y1="{ys[4]}" x2="{X}" y2="{ys[5]}" stroke="{ACCENT["red"]}" stroke-width="12" stroke-linecap="round" stroke-dasharray="2 22"/>')
        for i, (name, role, metric, c) in enumerate(CAREER):
            y = ys[i]
            doc.node(X, y, 14 if i == 4 else 11)
            doc.text(X + 34, y - 4, name, DISPLAY, 22, doc.t["ink"])
            doc.text(X + 34, y + 18, role, REG, 15, doc.t["muted"])
            doc.text(X + 34, y + 40, metric, SEMI, 16, doc.t["text"][c])
        here = (X, ys[4])
        doc.raw(f'<circle cx="{X}" cy="{ys[5]}" r="12" fill="{doc.t["bg"]}" stroke="{doc.t["ink"]}" stroke-width="4" stroke-dasharray="5 4"/>')
        doc.text(X + 34, ys[5] - 4, "2027", DISPLAY, 22, doc.t["ink"])
        doc.text(X + 34, ys[5] + 18, "open to new grad", REG, 15, doc.t["muted"])
    doc.raw(f'<circle class="hr" cx="{here[0]}" cy="{here[1]}" r="14" fill="none" stroke="{ACCENT["red"]}" stroke-width="3"/>')
    doc.css.append(".hr{transform-box:fill-box;transform-origin:center;animation:hr 2.4s ease-out infinite}"
                   "@keyframes hr{0%{transform:scale(1);opacity:.9}100%{transform:scale(2.4);opacity:0}}"
                   "@media (prefers-reduced-motion:reduce){.hr{animation:none;opacity:0}}")
    return doc.render()


# ------------------------------------------------------------------ cards


def status_pill(doc: Doc, item: dict, right: float, cy: float) -> None:
    st = item.get("status")
    if not st:
        return
    c = ACCENT[item["color"]]
    pw = width(st, SEMI, 12.5) + 34
    x = right - pw
    doc.raw(f'<rect x="{x:.1f}" y="{cy - 13}" width="{pw:.1f}" height="26" rx="13" fill="{c}" fill-opacity=".14" stroke="{c}" stroke-width="1.5"/>')
    doc.raw(f'<circle cx="{x + 14:.1f}" cy="{cy}" r="4" fill="{c}"/>')
    doc.text(x + 24, cy + 4.5, st, SEMI, 12.5, doc.t["text"][item["color"]])


def card(item: dict, theme: str, mobile: bool) -> str:
    t = THEMES[theme]
    c = item["color"]
    label = f"{item['title']}, {item['meta']}, {item['when']}. " + " ".join(p.replace("**", "") for p in item["points"])
    pad = 30 if mobile else 34
    body_size, lead = (16.5, 25) if mobile else (15.5, 24)

    def left_col(doc, x, y, w):
        """Title, meta, when, tags. Returns bottom y."""
        if doc:
            doc.raw(f'<path d="M{x} {y} L{x + 46} {y}" stroke="{ACCENT[c]}" stroke-width="8" stroke-linecap="round"/>')
        y += 38
        tsize = 27 if mobile else 26
        for ln in wrap(item["title"], w, tsize, DISPLAY, DISPLAY):
            if doc:
                doc.text(x, y, " ".join(word for word, _ in ln), DISPLAY, tsize, t["ink"])
            y += tsize + 4
        y += 2
        msize = 15 if mobile else 14.5
        for ln in wrap(item["meta"], w, msize, SEMI, SEMI):
            if doc:
                doc.text(x, y, " ".join(word for word, _ in ln), SEMI, msize, t["text"][c])
            y += 20
        y += 1
        if doc:
            doc.text(x, y, item["when"], MONO if "/" in item["when"] or ".app" in item["when"] else REG, 12.5 if "/" in item["when"] or ".app" in item["when"] else 14, t["muted"])
        if item["tags"]:
            y = pills(doc, x, y + 16, item["tags"], w, stroke=t["line"])
        return y

    def bullets(doc, x, y, w):
        for p in item["points"]:
            lines = wrap(p, w - 22, body_size)
            if doc:
                doc.raw(f'<circle cx="{x + 5}" cy="{y + 18 - body_size * 0.35:.1f}" r="4.5" fill="{t["bg"]}" stroke="{ACCENT[c]}" stroke-width="3"/>')
            for ln in lines:
                if doc:
                    draw_rich(doc, x + 22, y + 18, ln, body_size, t["muted"], t["ink"])
                y += lead
            y += 10
        return y - 10

    if mobile:
        W = 480
        inner = W - pad * 2
        h_left = left_col(None, pad, 26, inner)
        h = bullets(None, pad, h_left + 18, inner) + pad - 8
        doc = Doc(W, h, theme, label)
        status_pill(doc, item, W - pad, 26)
        y = left_col(doc, pad, 26, inner)
        bullets(doc, pad, y + 18, inner)
    else:
        W, lw, gap = 900, 270, 34
        rx = pad + lw + gap
        rw = W - rx - pad
        hl = left_col(None, pad, 30, lw)
        hr = bullets(None, rx, 30, rw)
        h = max(hl, hr) + pad - 4
        doc = Doc(W, h, theme, label)
        status_pill(doc, item, W - pad, 30)
        left_col(doc, pad, 30, lw)
        # bullets sit vertically centered against the left column
        off = max(0, (hl - hr) / 2)
        bullets(doc, rx, 30 + off, rw)
        doc.raw(f'<line x1="{pad + lw + gap / 2}" y1="{pad}" x2="{pad + lw + gap / 2}" y2="{h - pad}" stroke="{t["line"]}" stroke-width="1.5"/>')
    return doc.render()


# ------------------------------------------------------------------ stack


def stack(theme: str, mobile: bool) -> str:
    label = "Stack. " + ". ".join(f"{n}: {', '.join(i)}" for n, _, i in STACK)
    if not mobile:
        row, top = 96, 70
        doc = Doc(900, top + row * len(STACK), theme, label)
        for r, (name, c, items) in enumerate(STACK):
            y = top + r * row
            doc.text(40, y + 8, name, DISPLAY, 24, doc.t["text"][c])
            x0, x1 = 265, 840
            doc.raw(f'<line x1="{x0}" y1="{y}" x2="{x1}" y2="{y}" stroke="{ACCENT[c]}" stroke-width="10" stroke-linecap="round"/>')
            step = (x1 - x0 - 30) / (len(items) - 1)
            for i, it in enumerate(items):
                x = x0 + 15 + i * step
                doc.node(x, y, 8)
                doc.text(x, y + 32, it, SEMI, 15, doc.t["ink"], "middle")
        return doc.render()
    # mobile: each group is a colored line with its tools as pills underneath
    pad, y = 30, 26
    plan = []
    for name, c, items in STACK:
        plan.append((name, c, items, y))
        y = pills(None, pad, y + 30, items, 480 - pad * 2, size=15, font=SEMI, h=34, gap=10) + 28
    doc = Doc(480, y - 4, theme, label)
    for name, c, items, y0 in plan:
        doc.raw(f'<path d="M{pad} {y0} L{pad + 46} {y0}" stroke="{ACCENT[c]}" stroke-width="8" stroke-linecap="round"/>')
        doc.text(pad + 58, y0 + 8, name, DISPLAY, 22, doc.t["text"][c])
        pills(doc, pad, y0 + 30, items, 480 - pad * 2, size=15, stroke=ACCENT[c], font=SEMI, h=34, gap=10)
    return doc.render()


# ------------------------------------------------------------------ small pieces


def facts(theme: str, mobile: bool) -> str:
    label = ". ".join(f"{k} {v}" for k, v, _ in FACTS)
    if not mobile:
        W, H, pad = 900, 104, 34
        doc = Doc(W, H, theme, label)
        cw = (W - pad * 2) / len(FACTS)
        for i, (k, v, c) in enumerate(FACTS):
            x = pad + i * cw
            if i:
                doc.raw(f'<line x1="{x - 14:.1f}" y1="28" x2="{x - 14:.1f}" y2="{H - 28}" stroke="{doc.t["line"]}" stroke-width="1.5"/>')
            doc.raw(f'<circle cx="{x + 5}" cy="38" r="5" fill="{ACCENT[c]}"/>')
            doc.text(x + 18, 43, k, SEMI, 13.5, doc.t["muted"])
            doc.text(x, 76, v, DISPLAY, 22, doc.t["ink"])
    else:
        W, pad, rh = 480, 30, 74
        H = pad * 2 + rh * 2 - 12
        doc = Doc(W, H, theme, label)
        cw = (W - pad * 2) / 2
        for i, (k, v, c) in enumerate(FACTS):
            x, y = pad + (i % 2) * cw, pad + (i // 2) * rh
            doc.raw(f'<circle cx="{x + 5}" cy="{y + 9}" r="5" fill="{ACCENT[c]}"/>')
            doc.text(x + 18, y + 14, k, SEMI, 14.5, doc.t["muted"])
            doc.text(x, y + 46, v, DISPLAY, 22, doc.t["ink"])
    return doc.render()


def section(key: str, theme: str, mobile: bool) -> str:
    title, c = SECTIONS[key]
    W, H, size = (480, 64, 28) if mobile else (900, 72, 32)
    doc = Doc(W, H, theme, title)
    x = 24 if mobile else 30
    doc.text(x, H / 2 + size * 0.36, title, DISPLAY, size, doc.t["ink"])
    x1 = x + width(title, DISPLAY, size) + 22
    doc.raw(f'<path d="M{x1:.0f} {H / 2} L{W - 42} {H / 2}" stroke="{ACCENT[c]}" stroke-width="6" stroke-linecap="round"/>')
    doc.node(W - 38, H / 2, 8, ring=ACCENT[c])
    return doc.render()


def button(key: str, theme: str) -> str:
    label, c = BUTTONS[key]
    tw = width(label, DISPLAY, 18)
    W, H = tw + 64, 50
    doc = Doc(W, H, theme, label)
    dark = "#0E1A3D"
    doc.raw(f'<rect width="{W:.0f}" height="{H}" rx="25" fill="{ACCENT[c]}"/><circle cx="24" cy="25" r="5" fill="{dark}"/>')
    doc.text(40, 31.5, label, DISPLAY, 18, dark)
    return doc.render(panel=False)


def footer(theme: str, mobile: bool) -> str:
    a, b = "Say hi", C["links"]["email"]
    W, H = (480, 190) if mobile else (900, 200)
    doc = Doc(W, H, theme, f"{a} at {b}")
    hub = (190, 95) if mobile else (470, 100)
    ys = [15, 55, 95, 135, 175] if mobile else [20, 62, 100, 138, 180]
    for c, y0 in zip(["sky", "teal", "red", "amber", "pink"], ys):
        doc.raw(f'<path d="M-10 {y0} C{hub[0] * 0.45} {y0} {hub[0] * 0.65} {hub[1]} {hub[0]} {hub[1]}" fill="none" stroke="{ACCENT[c]}" stroke-width="{10 if mobile else 11}" stroke-linecap="round"/>')
    doc.raw(f'<circle cx="{hub[0]}" cy="{hub[1]}" r="20" fill="{doc.t["node"]}" stroke="{doc.t["ring"]}" stroke-width="{doc.t["rw"] + 1}"/>')
    if mobile:
        doc.text(234, 96, a, DISPLAY, 40, doc.t["ink"])
        doc.text(236, 126, b, SEMI, 15, doc.t["muted"])
    else:
        doc.text(530, 102, a, DISPLAY, 46, doc.t["ink"])
        doc.text(533, 136, b, SEMI, 18, doc.t["muted"])
    return doc.render()


# ------------------------------------------------------------------ main


def write_all(name: str, fn) -> None:
    for theme in THEMES:
        for mobile in (False, True):
            (OUT / f"{name}{'-m' if mobile else ''}-{theme}.svg").write_text(fn(theme, mobile))


def main() -> None:
    OUT.mkdir(exist_ok=True)
    for f in OUT.glob("*.svg"):
        if not f.name.startswith("live"):  # live panels belong to live.py
            f.unlink()
    write_all("hero", hero)
    write_all("career", career)
    write_all("stack", stack)
    write_all("facts", facts)
    write_all("footer", footer)
    for key in SECTIONS:
        write_all(f"h-{key}", lambda th, m, k=key: section(k, th, m))
    for item in JOBS:
        write_all(f"job-{item['key']}", lambda th, m, it=item: card(it, th, m))
    for item in PROJECTS:
        write_all(f"proj-{item['key']}", lambda th, m, it=item: card(it, th, m))
    write_all("edu", lambda th, m: card(EDUCATION, th, m))
    for key in BUTTONS:
        for theme in THEMES:
            (OUT / f"btn-{key}-{theme}.svg").write_text(button(key, theme))


if __name__ == "__main__":
    main()
