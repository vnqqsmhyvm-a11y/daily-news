#!/usr/bin/env python3
"""Render briefs/YYYY-MM-DD.md into the static site.

Outputs:
  index.html                 latest brief in full
  archive/index.html         every day, newest first, grouped by month
  YYYY/MM/DD/index.html      one page per day, with prev/next links
"""
import datetime as dt
import html
import re
import shutil
import sys
from pathlib import Path

import markdown

ROOT = Path(__file__).resolve().parent
BRIEFS = ROOT / "briefs"
SITE_TITLE = "Evening news brief"
NAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")

CSS = """
:root{color-scheme:light dark;--bg:#fbfaf7;--fg:#1d1d1f;--muted:#6b6b70;--rule:#e3e1dc;--link:#0b57d0;--card:#fff}
@media (prefers-color-scheme:dark){:root{--bg:#141416;--fg:#e9e9ec;--muted:#9a9aa2;--rule:#2c2c31;--link:#8ab4f8;--card:#1c1c1f}}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:18px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",system-ui,Roboto,"Helvetica Neue",Arial,sans-serif;font-kerning:normal}
.wrap{max-width:40rem;margin:0 auto;padding:max(1.25rem,env(safe-area-inset-top)) max(1.1rem,env(safe-area-inset-right)) 3rem max(1.1rem,env(safe-area-inset-left))}
header.site{display:flex;justify-content:space-between;align-items:baseline;gap:1rem;font-size:.9rem;color:var(--muted);border-bottom:1px solid var(--rule);padding-bottom:.6rem;margin-bottom:1.4rem}
header.site a{color:inherit;text-decoration:none}
header.site a:hover{color:var(--link)}
h1{font-size:1.6rem;line-height:1.25;margin:.2rem 0 1.2rem;letter-spacing:-.01em}
h2{font-size:1.15rem;margin:2rem 0 .6rem;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.04em}
.brief p{margin:0 0 1.05rem}
.brief ul,.brief ol{padding-left:1.3rem;margin:0 0 1.05rem}
.brief li{margin:.25rem 0}
.brief strong{font-weight:650}
a{color:var(--link);text-underline-offset:.15em}
nav.pager{display:flex;justify-content:space-between;gap:1rem;border-top:1px solid var(--rule);margin-top:2rem;padding-top:1rem;font-size:.95rem}
nav.pager .mid{text-align:center}
nav.pager span.off{color:var(--muted)}
.more{margin-top:2rem;padding-top:1rem;border-top:1px solid var(--rule);font-size:.95rem}
ul.days{list-style:none;padding:0;margin:0 0 1rem}
ul.days li{padding:.45rem 0;border-bottom:1px solid var(--rule)}
ul.days a{text-decoration:none}
ul.days a:hover{text-decoration:underline}
.muted{color:var(--muted)}
@media (min-width:48rem){body{font-size:19px}h1{font-size:1.9rem}}
"""


def load_briefs():
    out = []
    for p in sorted(BRIEFS.glob("*.md")):
        m = NAME_RE.match(p.name)
        if not m:
            print(f"skip {p.name}: not YYYY-MM-DD.md", file=sys.stderr)
            continue
        d = dt.date(int(m[1]), int(m[2]), int(m[3]))
        out.append((d, p.read_text(encoding="utf-8")))
    out.sort(key=lambda x: x[0])
    return out


LIST_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")


def prep(md_text):
    """Insert a blank line before a list that directly follows a paragraph,
    so '- item' lines render as a real list (Python-Markdown requires it)."""
    lines = md_text.replace("\r\n", "\n").split("\n")
    out = []
    for i, line in enumerate(lines):
        if LIST_RE.match(line) and out and out[-1].strip() and not LIST_RE.match(out[-1]) and not out[-1].startswith((" ", "\t")):
            out.append("")
        out.append(line)
    return "\n".join(out)


def render_md(md_text):
    return markdown.markdown(prep(md_text), extensions=["sane_lists", "nl2br", "smarty"], output_format="html5")


def long_date(d):
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


def day_path(d):
    return f"{d:%Y}/{d:%m}/{d:%d}/"


def page(title, body, base):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#fbfaf7" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#141416" media="(prefers-color-scheme: dark)">
<title>{html.escape(title)}</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
<header class="site"><a href="{base}">{SITE_TITLE}</a><a href="{base}archive/">Archive</a></header>
{body}
</div>
</body>
</html>
"""


def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def main():
    briefs = load_briefs()
    if not briefs:
        sys.exit("no briefs found in briefs/")

    # Remove previously generated day folders so deleted briefs disappear.
    for child in ROOT.iterdir():
        if child.is_dir() and re.fullmatch(r"\d{4}", child.name):
            shutil.rmtree(child)

    # Day pages
    base_day = "../../../"
    for i, (d, md) in enumerate(briefs):
        prev_d = briefs[i - 1][0] if i > 0 else None
        next_d = briefs[i + 1][0] if i + 1 < len(briefs) else None
        prev_html = (f'<a rel="prev" href="{base_day}{day_path(prev_d)}">&larr; {prev_d:%b} {prev_d.day}</a>'
                     if prev_d else '<span class="off">&larr; Older</span>')
        next_html = (f'<a rel="next" href="{base_day}{day_path(next_d)}">{next_d:%b} {next_d.day} &rarr;</a>'
                     if next_d else '<span class="off">Newer &rarr;</span>')
        body = (f'<main><h1>{long_date(d)}</h1>\n<article class="brief">\n{render_md(md)}\n</article></main>\n'
                f'<nav class="pager">{prev_html}<span class="mid"><a href="{base_day}">Home</a> · '
                f'<a href="{base_day}archive/">Archive</a></span>{next_html}</nav>')
        write(f"{day_path(d)}index.html", page(f"{long_date(d)} · {SITE_TITLE}", body, base_day))

    # Home page: latest brief
    d, md = briefs[-1]
    prev_link = ""
    if len(briefs) > 1:
        pd = briefs[-2][0]
        prev_link = f' · <a href="{day_path(pd)}">Previous: {pd:%b} {pd.day}</a>'
    body = (f'<main><h1>{long_date(d)}</h1>\n<article class="brief">\n{render_md(md)}\n</article></main>\n'
            f'<p class="more"><a href="archive/">All briefs ({len(briefs)})</a>{prev_link}'
            f' · <a href="{day_path(d)}">Permalink</a></p>')
    write("index.html", page(SITE_TITLE, body, ""))

    # Archive, newest first, grouped by month
    parts = ["<main><h1>Archive</h1>"]
    month = None
    for d, _ in reversed(briefs):
        key = (d.year, d.month)
        if key != month:
            if month is not None:
                parts.append("</ul>")
            parts.append(f"<h2>{d:%B} {d.year}</h2>\n<ul class=\"days\">")
            month = key
        parts.append(f'<li><a href="../{day_path(d)}">{long_date(d)}</a></li>')
    parts.append("</ul></main>")
    write("archive/index.html", page(f"Archive · {SITE_TITLE}", "\n".join(parts), "../"))

    write("robots.txt", "User-agent: *\nDisallow: /\n")
    write(".nojekyll", "")
    print(f"built {len(briefs)} briefs; latest {briefs[-1][0]}")


if __name__ == "__main__":
    main()
