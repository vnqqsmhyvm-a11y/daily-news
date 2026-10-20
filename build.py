#!/usr/bin/env python3
"""Render briefs/YYYY-MM-DD.md into the static site ("The Evening Brief").

Outputs:
  index.html                 latest edition in full
  archive/index.html         every edition, newest first, grouped by month, with teasers
  YYYY/MM/DD/index.html      one page per edition, with previous/next links

Static assets (committed, not generated): assets/site.css, assets/fonts/*.woff2
"""
import datetime as dt
import hashlib
import html
import re
import shutil
import sys
from pathlib import Path

import markdown

# Shared light/dark toggle snippet (copied verbatim into each site builder).
def theme_snippets(key, extra_css=""):
    head = ("<script>(function(){var t;try{t=localStorage.getItem('theme:%s')}catch(e){}"
            "if(t!=='light'&&t!=='dark')t=matchMedia('(prefers-color-scheme: dark)').matches?'dark':'light';"
            "document.documentElement.setAttribute('data-theme',t)})()</script>\n"
            "<style>.theme-toggle{position:fixed;top:calc(10px + env(safe-area-inset-top,0px));right:calc(10px + env(safe-area-inset-right,0px));z-index:1000;"
            "width:40px;height:40px;border-radius:50%%;border:1px solid rgba(127,127,127,.35);background:rgba(127,127,127,.14);"
            "-webkit-backdrop-filter:blur(8px);backdrop-filter:blur(8px);color:inherit;display:flex;align-items:center;justify-content:center;"
            "cursor:pointer;padding:0;-webkit-tap-highlight-color:transparent}"
            ".theme-toggle:hover{background:rgba(127,127,127,.24)}.theme-toggle svg{width:20px;height:20px;display:block}"
            "[data-theme=dark] .theme-toggle .moon,[data-theme=light] .theme-toggle .sun{display:none}"
            "@media print{.theme-toggle{display:none}}%s</style>") % (key, extra_css)
    btn = ('<button class="theme-toggle" type="button" aria-label="Toggle light/dark mode" title="Light/dark">'
           '<svg class="sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" aria-hidden="true">'
           '<circle cx="12" cy="12" r="4.5"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>'
           '<svg class="moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">'
           '<path d="M20.5 14.5A8.5 8.5 0 0 1 9.5 3.5a8.5 8.5 0 1 0 11 11z"/></svg></button>\n'
           "<script>(function(){var d=document.documentElement,k='theme:%s';"
           "function set(t,save){d.setAttribute('data-theme',t);if(save)try{localStorage.setItem(k,t)}catch(e){}"
           "var m=document.querySelector('meta[name=theme-color]:not([media])');if(m&&window.__tc)m.content=window.__tc[t]||m.content}"
           "document.querySelectorAll('.theme-toggle').forEach(function(b){b.addEventListener('click',function(){set(d.getAttribute('data-theme')==='dark'?'light':'dark',true)})});"
           "try{matchMedia('(prefers-color-scheme: dark)').addEventListener('change',function(e){var s;try{s=localStorage.getItem(k)}catch(x){}if(!s)set(e.matches?'dark':'light')})}catch(e){}"
           "})()</script>") % key
    return head, btn

THEME_HEAD, THEME_BTN = theme_snippets('news', 'html .dateline{padding-right:48px}')


ROOT = Path(__file__).resolve().parent
BRIEFS = ROOT / "briefs"
NAMEPLATE = "The Evening Brief"
DATELINE = "Tulsa, Oklahoma"
NAME_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})\.md$")
LIST_RE = re.compile(r"^\s*([-*+]|\d+[.)])\s+")
# "**Label**" alone on the first line of a paragraph (optionally followed by . or :)
STANDALONE_RE = re.compile(r"^\*\*([^*\n]{1,60}?)\*\*[.:]?\s*$")
# "**Label.** text" or "**Label**: text"
INLINE_RE = re.compile(r"^\*\*([^*\n]{1,60}?)(?:[.:]\*\*|\*\*[.:])[ \t]*")

CSS_PATH = ROOT / "assets" / "site.css"
CSS_VER = hashlib.sha1(CSS_PATH.read_bytes()).hexdigest()[:10] if CSS_PATH.exists() else "0"


# ---------- parsing ----------

def load_briefs():
    out = []
    for p in sorted(BRIEFS.glob("*.md")):
        m = NAME_RE.match(p.name)
        if not m:
            print(f"skip {p.name}: not YYYY-MM-DD.md", file=sys.stderr)
            continue
        out.append((dt.date(int(m[1]), int(m[2]), int(m[3])), p.read_text(encoding="utf-8")))
    out.sort(key=lambda x: x[0])
    return out


def prep(md_text):
    """Normalise newlines and put a blank line before a list that directly
    follows a paragraph, so '- item' lines render as a real list."""
    lines = md_text.replace("\r\n", "\n").split("\n")
    out = []
    for line in lines:
        if (LIST_RE.match(line) and out and out[-1].strip()
                and not LIST_RE.match(out[-1]) and not out[-1].startswith((" ", "\t"))):
            out.append("")
        out.append(line)
    return "\n".join(out)


def split_sections(md_text):
    """Split a brief into [{'label': str|None, 'md': str}] using leading bold labels.
    A list block never starts a section, so lists stay inside the section above."""
    blocks = [b for b in re.split(r"\n[ \t]*\n", prep(md_text).strip()) if b.strip()]
    sections, cur = [], None
    for b in blocks:
        label, rest = None, None
        first, _, tail = b.partition("\n")
        m = STANDALONE_RE.match(first)
        if m:
            label, rest = m[1], tail
        else:
            m = INLINE_RE.match(b)
            if m:
                label, rest = m[1], b[m.end():]
        if label is not None:
            cur = {"label": label.strip().rstrip(".:").strip(), "md": []}
            sections.append(cur)
            if rest.strip():
                cur["md"].append(rest.strip("\n"))
        else:
            if cur is None:
                cur = {"label": None, "md": []}
                sections.append(cur)
            cur["md"].append(b)
    sections = [s for s in sections if s["md"]]
    for s in sections:
        s["md"] = "\n\n".join(s["md"])
    if not sections:
        sections = [{"label": None, "md": md_text}]
    return sections


def render_md(md_text):
    return markdown.markdown(md_text, extensions=["sane_lists", "nl2br", "smarty"], output_format="html5")


def plain(md_text):
    h = render_md(md_text)
    t = re.sub(r"</?(?:p|li|ul|ol|br|h\d)\b[^>]*>", " ", h)
    t = re.sub(r"<[^>]+>", "", t)
    return re.sub(r"\s+", " ", html.unescape(t)).strip()


def teaser(md_text, limit=170):
    first_para = re.split(r"\n[ \t]*\n", md_text.strip())[0]
    t = plain(first_para)
    if len(t) <= limit:
        return t
    cut = t[:limit].rsplit(" ", 1)[0].rstrip(",;:—–- ")
    return cut + "…"


def slugify(s, used):
    base = re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-") or "section"
    slug, n = base, 2
    while slug in used:
        slug, n = f"{base}-{n}", n + 1
    used.add(slug)
    return slug


# ---------- rendering ----------

def long_date(d):
    return f"{d:%A}, {d:%B} {d.day}, {d.year}"


def short_date(d):
    return f"{d:%a}, {d:%b} {d.day}"


def day_path(d):
    return f"{d:%Y}/{d:%m}/{d:%d}/"


def esc(s):
    return html.escape(s, quote=True)


def shell(title, base, band_html, main_html, footer_html=""):
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
{THEME_HEAD}
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="robots" content="noindex, nofollow">
<meta name="referrer" content="no-referrer">
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f5f0e6" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#171512" media="(prefers-color-scheme: dark)">
<title>{esc(title)}</title>
<link rel="preload" href="{base}assets/fonts/source-serif-4-latin-400-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{base}assets/fonts/playfair-display-latin-900-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{base}assets/fonts/oswald-latin-500-normal.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{base}assets/site.css?v={CSS_VER}">
</head>
<body>
{THEME_BTN}
<div class="page">
<header class="masthead">
<div class="dateline"><span>{DATELINE}</span><a href="{base}archive/">Archive</a></div>
<div class="nameplate"><a href="{base}">{NAMEPLATE}</a></div>
<div class="band">{band_html}</div>
</header>
{main_html}
{footer_html}
</div>
</body>
</html>
"""


def edition_html(d, md, base, prev_d, next_d, extra_mid=""):
    sections = split_sections(md)
    used = set()
    for i, s in enumerate(sections):
        if s["label"] is None:
            s["label"] = "The Lead" if len(sections) > 1 else "Tonight’s Brief"
        s["id"] = slugify(s["label"], used)

    toc = ""
    if len(sections) > 1:
        items = "".join(f'<li><a href="#{s["id"]}">{esc(s["label"])}</a></li>' for s in sections)
        toc = f'<nav class="toc" aria-label="In this edition"><span class="lbl">In this edition</span><ol>{items}</ol></nav>'

    def sec(s, lead=False):
        cls = "section lead" if lead else "section"
        if lead and len(plain(s["md"])) > 1100:
            cls += " long"  # only long lead stories flow into two columns on desktop
        kick = ' data-kick="Top story"' if lead else ""
        return (f'<section class="{cls}" id="{s["id"]}">\n'
                f'<h2 class="kicker"{kick}>{esc(s["label"])}</h2>\n'
                f'<div class="body">\n{render_md(s["md"])}\n</div>\n</section>')

    lead = sec(sections[0], lead=True)
    rest = "\n".join(sec(s) for s in sections[1:])
    rest_html = f'<div class="rest">\n{rest}\n</div>' if rest else ""
    main = f'{toc}\n<main>\n<article class="edition">\n{lead}\n{rest_html}\n</article>\n</main>'

    prev_html = (f'<a class="prev" rel="prev" href="{base}{day_path(prev_d)}"><span class="small">Previous edition</span>&larr; {short_date(prev_d)}</a>'
                 if prev_d else '<span class="prev off"><span class="small">Previous edition</span>—</span>')
    next_html = (f'<a class="next" rel="next" href="{base}{day_path(next_d)}"><span class="small">Next edition</span>{short_date(next_d)} &rarr;</a>'
                 if next_d else '<span class="next off"><span class="small">Next edition</span>—</span>')
    mid = (f'<span class="mid"><span class="small">The Evening Brief</span>'
           f'<a href="{base}">Front page</a><span class="dot">·</span>'
           f'<a href="{base}archive/">Archive</a>{extra_mid}</span>')
    footer = (f'<footer class="footer"><nav aria-label="Editions">{prev_html}{mid}{next_html}</nav>'
              f'<p class="colophon">{NAMEPLATE} · {DATELINE} · {long_date(d)}</p></footer>')
    band = f'<span>{long_date(d)}</span><span class="sep">·</span><span>Evening Edition</span>'
    return band, main, footer, sections


def write(rel, content):
    p = ROOT / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def main():
    briefs = load_briefs()
    if not briefs:
        sys.exit("no briefs found in briefs/")

    for child in ROOT.iterdir():  # remove old generated day folders
        if child.is_dir() and re.fullmatch(r"\d{4}", child.name):
            shutil.rmtree(child)

    meta = {}
    for i, (d, md) in enumerate(briefs):
        prev_d = briefs[i - 1][0] if i > 0 else None
        next_d = briefs[i + 1][0] if i + 1 < len(briefs) else None
        base = "../../../"
        band, main_html, footer, sections = edition_html(d, md, base, prev_d, next_d)
        write(f"{day_path(d)}index.html",
              shell(f"{long_date(d)} · {NAMEPLATE}", base, band, main_html, footer))
        meta[d] = sections

    # Front page = latest edition
    d, md = briefs[-1]
    prev_d = briefs[-2][0] if len(briefs) > 1 else None
    band, main_html, footer, _ = edition_html(
        d, md, "", prev_d, None,
        extra_mid=f'<span class="dot">·</span><a href="{day_path(d)}">Permalink</a>')
    write("index.html", shell(NAMEPLATE, "", band, main_html, footer))

    # Archive
    parts = [f'<main class="archive archive-wrap"><h1>The Archive</h1>'
             f'<p class="count">{len(briefs)} editions</p>']
    month = None
    for d, _ in reversed(briefs):
        if (d.year, d.month) != month:
            if month is not None:
                parts.append("</ul>")
            parts.append(f'<h2 class="month">{d:%B} {d.year}</h2>\n<ul class="days">')
            month = (d.year, d.month)
        s0 = meta[d][0]
        parts.append(f'<li><a href="../{day_path(d)}"><span class="d">{long_date(d)}</span>'
                     f'<span class="k">{esc(s0["label"])}</span>'
                     f'<span class="t">{esc(teaser(s0["md"]))}</span></a></li>')
    parts.append("</ul></main>")
    footer = (f'<footer class="footer"><nav aria-label="Editions"><span class="prev"></span>'
              f'<span class="mid"><span class="small">The Evening Brief</span><a href="../">Front page</a></span><span class="next"></span></nav>'
              f'<p class="colophon">{NAMEPLATE} · {DATELINE}</p></footer>')
    band = f'<span>Every edition</span><span class="sep">·</span><span>Newest first</span>'
    write("archive/index.html", shell(f"Archive · {NAMEPLATE}", "../", band, "\n".join(parts), footer))

    write("robots.txt", "User-agent: *\nDisallow: /\n")
    write(".nojekyll", "")
    print(f"built {len(briefs)} briefs; latest {briefs[-1][0]}")


if __name__ == "__main__":
    main()
