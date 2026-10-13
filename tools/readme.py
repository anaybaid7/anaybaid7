"""Writes README.md. Every image is a <picture> that swaps in the mobile and
light/dark variants drawn by build.py.  Run: python tools/readme.py"""
from pathlib import Path

import build

ROOT = Path(__file__).resolve().parent.parent


def pic(name: str, alt: str, href: str | None = None, mobile: bool = True) -> str:
    srcs = []
    if mobile:
        srcs += [f'<source media="(max-width: 768px) and (prefers-color-scheme: dark)" srcset="assets/{name}-m-dark.svg">',
                 f'<source media="(max-width: 768px)" srcset="assets/{name}-m-light.svg">']
    srcs.append(f'<source media="(prefers-color-scheme: dark)" srcset="assets/{name}-dark.svg">')
    img = f'<img src="assets/{name}-light.svg" width="100%" alt="{alt}">'
    out = f"<picture>{''.join(srcs)}{img}</picture>"
    return f'<a href="{href}">{out}</a>' if href else out


def button(key: str, href: str) -> str:
    label = build.BUTTONS[key][0]
    return (f'<a href="{href}"><picture><source media="(prefers-color-scheme: dark)" srcset="assets/btn-{key}-dark.svg">'
            f'<img src="assets/btn-{key}-light.svg" height="44" alt="{label}"></picture></a>')


def details(summary: str, inner: list[str]) -> str:
    return f"<details>\n<summary><b>{summary}</b></summary>\n<br>\n\n" + "\n\n".join(inner) + "\n\n</details>"


def alt(item: dict) -> str:
    return f"{item['title']}, {item['meta']}, {item['when']}. " + " ".join(p.replace("**", "") for p in item["points"])


L = build.C["links"]
LINKS = {p["key"]: p.get("link") for p in build.PROJECTS}


def main() -> None:
    b = []
    b.append(pic("hero", f"{build.NAME}. " + build.HERO_SUB, L["portfolio"]))
    b.append(pic("facts", ". ".join(f"{k} {v}" for k, v, _ in build.FACTS)))
    b.append('<p align="center">' + " ".join([
        button("resume", L["resume"]),
        button("portfolio", L["portfolio"]),
        button("linkedin", L["linkedin"]),
        button("email", "mailto:" + L["email"]),
    ]) + "</p>")

    b.append(pic("h-experience", "Where I've been"))
    b.append(pic("career", "Career. " + ", ".join(f"{n}, {r}" for n, r, *_ in build.CAREER) + ". Open to new grad roles in 2027."))
    for job in build.JOBS[:build.C["jobs_shown"]]:
        b.append(pic(f"job-{job['key']}", alt(job)))
    earlier = build.JOBS[build.C["jobs_shown"]:]
    b.append(details("Earlier roles, " + ", ".join(j["title"] for j in earlier),
                     [pic(f"job-{j['key']}", alt(j)) for j in earlier]))

    b.append("<br>")
    b.append(pic("h-projects", "Things I've built"))
    for p in build.PROJECTS[:build.C["projects_shown"]]:
        b.append(pic(f"proj-{p['key']}", alt(p), LINKS.get(p["key"])))
    more = build.PROJECTS[build.C["projects_shown"]:]
    b.append(details("More projects, " + ", ".join(p["title"] for p in more),
                     [pic(f"proj-{p['key']}", alt(p), LINKS.get(p["key"])) for p in more]))

    b.append(pic("live", "Lately on GitHub, recent repositories and contributions over the last six months"))

    b.append("<br>")
    b.append(pic("h-stack", "Stack"))
    b.append(pic("stack", "Stack. " + ". ".join(f"{n}: {', '.join(i)}" for n, _, i in build.STACK)))

    b.append("<br>")
    b.append(pic("h-education", "Education"))
    b.append(pic("edu", alt(build.EDUCATION)))

    b.append("<br>")
    b.append(pic("footer", "Say hi at " + L["email"], "mailto:" + L["email"]))
    (ROOT / "README.md").write_text("\n\n".join(b) + "\n")


if __name__ == "__main__":
    main()
