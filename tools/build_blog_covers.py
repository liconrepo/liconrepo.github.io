#!/usr/bin/env python3
"""Make the cover picture and the thumbnail for every blog page, and wire them into the HTML.

  blog/img/cover/<page>.jpg    1200x630, shown at the top of the article and used when the link is shared (og:image)
  blog/img/thumb/<page>.jpg    480x252, shown on the home page's article cards
  blog/img/cover/series-<id>.jpg, blog/img/thumb/series-<id>.jpg      the same for each series card

The pictures are drawn from each page's own title, kicker (series and part number) and tags, so nothing has to be
made by hand. Colours come from the page's family (Android architecture, Claude Code, DSA...); the pattern is
different for every page.

Run from the repository root after adding a post, then commit the new pictures:

    python3 tools/build_blog_covers.py

Needs Pillow (pip install pillow) and, for the lettering, a bold sans-serif font (macOS ships with one; on Linux
DejaVu Sans Bold is used). It is safe to run again: pictures are redrawn and the HTML is only touched where a page
does not have its cover yet. It is not part of the GitHub Action because the pictures are committed.
"""
import hashlib, html, math, re, sys
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://liconrepo.github.io/"
W, H, SS = 1200, 630, 2                      # picture size, and the supersampling factor for smooth edges

# page-name prefix -> (gradient start, gradient end, accent)
FAMILIES = [
    ("android-arch", ("#0b1b3a", "#1d4ed8", "#7dd3fc")),
    ("claude-md",    ("#2a1308", "#c2410c", "#fdba74")),
    ("codex",        ("#04201c", "#0f766e", "#5eead4")),
    ("dsa",          ("#1e1038", "#6d28d9", "#c4b5fd")),
    ("mds",          ("#2f0a1d", "#be185d", "#f9a8d4")),
    ("firebase",     ("#2b1a02", "#b45309", "#fcd34d")),
    ("android",      ("#0a1f2e", "#0369a1", "#7dd3fc")),
    ("ai-",          ("#14102e", "#4338ca", "#a5b4fc")),
    ("private-ai",   ("#14102e", "#4338ca", "#a5b4fc")),
    ("llm",          ("#0d1f2d", "#0e7490", "#67e8f9")),
    ("git",          ("#2a0f0a", "#b91c1c", "#fca5a5")),
    ("clean",        ("#0c2214", "#15803d", "#86efac")),
    ("solid",        ("#0c2214", "#15803d", "#86efac")),
    ("design",       ("#1f1d0a", "#a16207", "#fde047")),
    ("patterns",     ("#1f1d0a", "#a16207", "#fde047")),
]
DEFAULT = ("#111827", "#334155", "#cbd5e1")

FONT_FILES = [  # (path, index of the bold face) in order of preference
    ("/System/Library/Fonts/Avenir Next.ttc", 0), ("/System/Library/Fonts/HelveticaNeue.ttc", 1),
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 0), ("/Library/Fonts/Arial Bold.ttf", 0),
]


def font(size):
    for path, idx in FONT_FILES:
        if Path(path).exists():
            return ImageFont.truetype(path, size * SS, index=idx)
    sys.exit("No bold font found: add one to FONT_FILES in tools/build_blog_covers.py")


def rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def family(name):
    for prefix, colours in FAMILIES:
        if name.startswith(prefix):
            return colours
    return DEFAULT


def wrap(draw, text, fnt, width):
    lines, line = [], ""
    for word in text.split():
        trial = (line + " " + word).strip()
        if draw.textlength(trial, font=fnt) <= width or not line:
            line = trial
        else:
            lines.append(line)
            line = word
    return lines + [line] if line else lines


def draw_cover(name, title, kicker, tags, badge, fam=None):
    c1, c2, accent = (rgb(x) for x in family(fam or name))
    seed = int(hashlib.sha1(name.encode()).hexdigest(), 16)
    w, h = W * SS, H * SS
    # diagonal gradient: four corner colours, smoothly blended
    mix = lambda t: tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))
    corners = Image.new("RGB", (2, 2))
    corners.putdata([mix(0), mix(0.65), mix(0.35), mix(1)])
    img = corners.resize((w, h), Image.BILINEAR)
    # a pattern that is different for every page: rings and a dot grid
    over = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(over)
    cx = w * (0.62 + (seed % 30) / 100)
    cy = h * (0.15 + ((seed >> 8) % 60) / 100)
    for i in range(1, 9):
        r = i * 95 * SS
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=accent + (34,), width=2 * SS)
    gx, gy = (seed >> 16) % 40, (seed >> 24) % 40
    for ix in range(8):
        for iy in range(5):
            x, y = (w - 330 * SS) + ix * 40 * SS + gx * SS // 4, 60 * SS + iy * 40 * SS + gy * SS // 4
            d.ellipse([x - 3 * SS, y - 3 * SS, x + 3 * SS, y + 3 * SS], fill=accent + (70,))
    img = Image.alpha_composite(img.convert("RGBA"), over)
    d = ImageDraw.Draw(img)

    pad = 72 * SS
    glass = Image.new("RGBA", (w, h), (0, 0, 0, 0))          # translucent shapes go here, then are blended in once
    g = ImageDraw.Draw(glass)
    kfont, bfont, tf2, sfont = font(26), font(30), font(23), font(22)
    badge_w = d.textlength(badge, font=bfont) + 44 * SS + 24 * SS if badge else 0
    kick = (kicker or "Article").replace(" · ", "  ·  ").upper()
    while d.textlength(kick, font=kfont) > w - 2 * pad - badge_w and len(kick) > 4:     # never run into the part badge
        kick = kick[:-2].rstrip(" ·,") + "…" if not kick.endswith("…") else kick[:-2] + "…"
    if badge:                                                                                        # "PART 3 / 9"
        bx, by = w - pad - (badge_w - 24 * SS), 60 * SS
        g.rounded_rectangle([bx, by, w - pad, by + 62 * SS], radius=31 * SS, fill=(0, 0, 0, 90), outline=accent + (200,), width=2 * SS)
    tag_boxes, x = [], pad
    for t in tags[:4]:
        tw = d.textlength(t, font=tf2)
        if x + tw + 32 * SS > w - pad:
            break
        g.rounded_rectangle([x, 500 * SS, x + tw + 32 * SS, 542 * SS], radius=21 * SS, fill=(255, 255, 255, 28), outline=(255, 255, 255, 90), width=SS)
        tag_boxes.append((x + 16 * SS, t))
        x += tw + 32 * SS + 12 * SS
    g.line([pad, 568 * SS, w - pad, 568 * SS], fill=(255, 255, 255, 50), width=SS)
    img = Image.alpha_composite(img, glass)
    d = ImageDraw.Draw(img)

    d.rounded_rectangle([pad, 66 * SS, pad + 54 * SS, 72 * SS], radius=3 * SS, fill=accent)      # accent bar
    d.text((pad, 92 * SS), kick, font=kfont, fill=accent)
    if badge:
        d.text((bx + 22 * SS, by + 12 * SS), badge, font=bfont, fill=(255, 255, 255))

    # the title, as large as fits in five lines
    maxw, top, bottom = w - 2 * pad, 170 * SS, 470 * SS
    for size in range(68, 34, -2):
        tf = font(size)
        lines = wrap(d, title, tf, maxw)
        lh = int(size * 1.18) * SS
        if len(lines) * lh <= bottom - top:
            break
    else:
        lines = lines[:int((bottom - top) // lh)]
        lines[-1] = lines[-1].rstrip(" .,:;") + "…"
    y = top
    for ln in lines:
        d.text((pad, y), ln, font=tf, fill=(255, 255, 255))
        y += lh

    for tx, t in tag_boxes:
        d.text((tx, 507 * SS), t, font=tf2, fill=(238, 238, 242))
    d.text((pad, 582 * SS), "Khairul Alam", font=font(26), fill=(255, 255, 255))
    site = "liconrepo.github.io"
    d.text((w - pad - d.textlength(site, font=sfont), 585 * SS), site, font=sfont, fill=(205, 205, 214))
    return img.convert("RGB").resize((W, H), Image.LANCZOS)


def save(img, name):
    for sub, size, q in (("cover", (W, H), 86), ("thumb", (480, 252), 82)):
        d = ROOT / "blog" / "img" / sub
        d.mkdir(parents=True, exist_ok=True)
        (img if size == (W, H) else img.resize(size, Image.LANCZOS)).save(d / (name + ".jpg"), quality=q, optimize=True, progressive=True)


# ---- reading the pages ----
def clean(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", s))).strip()


def plain(s):
    """Drop emoji: the lettering font has no glyphs for them, so they would be drawn as empty boxes."""
    return re.sub(r"\s+", " ", re.sub("[\U0001F000-\U0001FFFF\u2600-\u27BF\uFE0F\u200d]", "", s)).strip()


def read_page(path):
    src = path.read_text(encoding="utf-8")
    h1 = re.search(r"<h1[^>]*>(.*?)</h1>", src, re.S)
    kick = re.search(r'<p class="kicker">(.*?)</p>', src, re.S)
    desc = re.search(r'<meta name="description" content="([^"]*)"', src)
    tags = [clean(t) for t in re.findall(r'<span class="tag">(.*?)</span>', src, re.S)]
    kicker = clean(kick.group(1)) if kick else ""
    part = re.search(r"Part (\d+) of (\d+)", kicker)
    return {
        "name": path.stem, "src": src, "title": clean(h1.group(1)) if h1 else path.stem,
        "kicker": re.sub(r"\s*·\s*Part \d+ of \d+", "", kicker), "tags": tags,
        "desc": html.unescape(desc.group(1)) if desc else "", "badge": "PART %s / %s" % part.groups() if part else "",
    }


COVER_CSS = """    /* cover picture (tools/build_blog_covers.py) */
    .cover { display: block; width: 100%; height: auto; aspect-ratio: 1200 / 630; border-radius: 14px; border: 1px solid var(--border); margin: 26px 0 6px; background: var(--surface); }
"""


def patch_page(p, has_cover):
    src, name = p["src"], p["name"]
    url = SITE + "blog/" + name + ".html"
    img = SITE + "blog/img/cover/" + name + ".jpg"
    if 'property="og:image"' not in src:
        tags = [
            '<meta property="og:type" content="article" />',
            '<meta property="og:site_name" content="Khairul Alam" />',
            '<meta property="og:title" content="%s" />' % html.escape(p["title"]),
            '<meta property="og:description" content="%s" />' % html.escape(p["desc"]),
            '<meta property="og:url" content="%s" />' % url,
            '<meta property="og:image" content="%s" />' % img,
            '<meta property="og:image:width" content="1200" />',
            '<meta property="og:image:height" content="630" />',
            '<meta name="twitter:card" content="summary_large_image" />',
            '<meta name="twitter:image" content="%s" />' % img,
        ]
        src = re.sub(r'(<meta name="description"[^>]*>\n)', lambda m: m.group(1) + "".join("  %s\n" % t for t in tags), src, count=1)
    if has_cover and 'class="cover"' not in src:
        if ".cover {" not in src:
            src = src.replace("</style>", COVER_CSS + "  </style>", 1)
        tag = '    <img class="cover" src="img/cover/%s.jpg" width="1200" height="630" alt="Cover: %s" fetchpriority="high" />\n' % (name, html.escape(p["title"], quote=True))
        src, n = re.subn(r'(<div class="tags">.*?</div>\n)', lambda m: m.group(1) + tag, src, count=1, flags=re.S)
        if not n:
            print("WARNING no tags row in", name, file=sys.stderr)
    if src != p["src"]:
        (ROOT / "blog" / (name + ".html")).write_text(src, encoding="utf-8")
        return True
    return False


# ---- the home page ----
THUMB_CSS = """    .blog-thumb { display: block; width: calc(100% + 40px); max-width: none; height: auto; aspect-ratio: 1200 / 630; object-fit: cover; margin: -20px -20px 14px; border-bottom: 1px solid var(--border); background: var(--surface); }
    .series-card .blog-thumb { width: 100%; max-width: 380px; margin: 0 0 14px; border: 1px solid var(--border); border-radius: 10px; }
"""


def patch_home(series):
    path = ROOT / "index.html"
    src = path.read_text(encoding="utf-8")
    orig = src
    if ".series-card .blog-thumb" not in src:                      # replaces an older version of the rule, if there is one
        src = re.sub(r"    \.blog-thumb \{.*?\n(    \.series-card \.blog-thumb \{.*?\n)?", "", src, flags=re.S) if ".blog-thumb {" in src else src
        src = src.replace("    .blog-idx {", THUMB_CSS + "    .blog-idx {", 1)

    def thumb(name, alt):
        return '<img class="blog-thumb" src="blog/img/thumb/%s.jpg" width="480" height="252" alt="%s" loading="lazy" decoding="async" />\n        ' % (name, html.escape(alt, quote=True))

    src = re.sub(r'(<a href="blog/([a-z0-9-]+)\.html" class="blog-card[^"]*">\s*\n\s*)(?!<img class="blog-thumb")(<div class="blog-idx">)', lambda m: m.group(1) + thumb(m.group(2), "") + m.group(3) if (ROOT / "blog" / "img" / "thumb" / (m.group(2) + ".jpg")).exists() else m.group(0), src)
    for sid in series:
        src = re.sub(r'(<div class="series-card[^"]*">\s*\n\s*)(?!<img class="blog-thumb")(<div class="blog-idx">(?:(?!</div>\s*<div class="series-parts).)*?id="series-%s")' % sid, lambda m: m.group(1) + thumb("series-" + sid, "") + m.group(2), src, count=1, flags=re.S)
    if src != orig:
        path.write_text(src, encoding="utf-8")
        return True
    return False


def main():
    pages = [read_page(p) for p in sorted((ROOT / "blog").glob("*.html"))]
    changed = 0
    for p in pages:
        save(draw_cover(p["name"], plain(p["title"]), p["kicker"], p["tags"], p["badge"]), p["name"])
        changed += patch_page(p, has_cover=bool(p["kicker"]))      # tool pages without a kicker (the LLM list) only get the share picture
        print("%-58s %s" % (p["name"], p["badge"] or "-"))

    home = (ROOT / "index.html").read_text(encoding="utf-8")
    series = {}
    for m in re.finditer(r'<div class="series-card[^"]*">(.*?)<div class="series-parts" id="series-([a-z0-9]+)"', home, re.S):
        body, sid = m.groups()
        title = clean(re.search(r'<div class="blog-title series-title">(.*?)</div>', body, re.S).group(1))
        count = clean(re.search(r'<div class="blog-idx">(.*?)<', body, re.S).group(1))
        first = re.search(r'<a class="series-part" href="blog/([a-z0-9-]+)\.html"', home[m.end():])
        tags = next((p["tags"] for p in pages if first and p["name"] == first.group(1)), [])
        series[sid] = (title, count, tags, first.group(1) if first else sid)
    for sid, (title, count, tags, first) in series.items():
        save(draw_cover("series-" + first, title, count, tags, "", fam=first), "series-" + sid)
        print("series-%-51s %s" % (sid, count))
    if patch_home(series):
        changed += 1
    print("Done. %d files changed (HTML)." % changed)


if __name__ == "__main__":
    main()
