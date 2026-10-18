#!/usr/bin/env python3
"""Build the generated site files:

  data/search/search-data.js
                     everything the site search looks through, as one script: the full text of every
                     article in blog/ (split at headings) plus the home page's own content (experience,
                     skills, open source, education...). It is a script rather than JSON so search also
                     works when a page is opened straight from disk (file://), where fetch() is blocked.
                     Loaded by data/search/search.js on the home page and on every blog page.
  sitemap.xml        every page of the site, for Google and other search engines

Run from the repository root after adding or editing a post:

    python3 tools/build_search_index.py

The GitHub Action in .github/workflows/search-index.yml does this automatically.
"""
import json, re, subprocess, sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SITE = "https://liconrepo.github.io/"
BLOCK = {"p", "div", "li", "ul", "ol", "tr", "td", "th", "table", "pre", "br", "section", "article",
         "figure", "figcaption", "details", "summary", "blockquote", "h1", "h2", "h3", "h4", "main", "text"}
SKIP = {"script", "style", "nav", "footer", "head", "noscript"}


class Extract(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.in_main = False
        self.have_main = False
        self.title = ""
        self.kicker = ""
        self.cur = {"h": "", "id": "", "t": []}
        self.segs = []
        self.head = None          # collecting heading text: [tag, id, parts]
        self.grab = None          # 'h1' / 'kicker' / 'title'
        self.buf = []

    # -- helpers
    def _flush(self):
        text = re.sub(r"\s+", " ", " ".join(self.cur["t"])).strip()
        if text or self.cur["h"]:
            self.segs.append({"h": self.cur["h"], "id": self.cur["id"], "x": text})
        self.cur = {"h": "", "id": "", "t": []}

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in SKIP:
            self.skip += 1
            return
        if tag == "title" and not self.title:
            self.grab = "title"; self.buf = []
        if tag == "main":
            self.in_main = True; self.have_main = True
        if self.skip or not self.in_main:
            return
        if tag == "h1":
            self.grab = "h1"; self.buf = []
        elif tag in ("h2", "h3"):
            self._flush()
            self.head = [tag, a.get("id", ""), []]
        elif tag == "p" and "kicker" in (a.get("class") or ""):
            self.grab = "kicker"; self.buf = []
        if tag in BLOCK:
            self.cur["t"].append(" ")

    def handle_endtag(self, tag):
        if tag in SKIP:
            self.skip = max(0, self.skip - 1)
            return
        if tag == "title" and self.grab == "title":
            self.title = " ".join(self.buf).strip(); self.grab = None
        if tag == "main":
            self.in_main = False
        if self.skip or not self.in_main:
            return
        if tag == "h1" and self.grab == "h1":
            self.title = re.sub(r"\s+", " ", " ".join(self.buf)).strip(); self.grab = None
        elif tag == "p" and self.grab == "kicker":
            self.kicker = re.sub(r"\s+", " ", " ".join(self.buf)).strip(); self.grab = None
        elif tag in ("h2", "h3") and self.head and self.head[0] == tag:
            self.cur = {"h": re.sub(r"\s+", " ", " ".join(self.head[2])).strip(), "id": self.head[1], "t": []}
            self.head = None
        if tag in BLOCK:
            self.cur["t"].append(" ")

    def handle_data(self, data):
        if self.grab:
            self.buf.append(data)
        if self.skip or not self.in_main:
            return
        if self.head is not None:
            self.head[2].append(data)
        elif self.grab != "h1":
            self.cur["t"].append(data)


def build():
    out = []
    for path in sorted((ROOT / "blog").glob("*.html")):
        html = path.read_text(encoding="utf-8")
        p = Extract()
        p.feed(html)
        p._flush()
        if not p.have_main:
            print("WARNING no <main> in", path.name, file=sys.stderr)
        title = p.title.replace(" — Khairul Alam", "").strip() or path.stem
        segs = [s for s in p.segs if s["x"] or s["h"]]
        words = sum(len(s["x"].split()) for s in segs)
        out.append({"u": "blog/" + path.name, "t": title, "k": p.kicker, "s": segs})
        print(f"{path.name:58s} {words:6d} words, {len(segs):3d} sections")
    build_data_js(out)


# ---- the home page's own content, for the search on blog pages ----
VOID = {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta", "source", "track", "wbr", "path", "circle", "rect", "line"}


class Node:
    def __init__(self, tag, attrs, parent):
        self.tag, self.attrs, self.parent, self.kids = tag, dict(attrs), parent, []

    def classes(self):
        return (self.attrs.get("class") or "").split()

    def text(self):
        return "".join(k if isinstance(k, str) else k.text() for k in self.kids)

    def walk(self):
        for k in self.kids:
            if isinstance(k, Node):
                yield k
                yield from k.walk()

    def has(self, cls):
        return cls in self.classes()

    def first(self, cls=None, tag=None):
        for n in self.walk():
            if (cls is None or n.has(cls)) and (tag is None or n.tag == tag):
                return n
        return None


class Tree(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", [], None)
        self.cur = self.root
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        n = Node(tag, attrs, self.cur)
        self.cur.kids.append(n)
        if tag in ("script", "style"):
            self.skip += 1
        if tag not in VOID:
            self.cur = n

    def handle_startendtag(self, tag, attrs):
        self.cur.kids.append(Node(tag, attrs, self.cur))

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self.skip = max(0, self.skip - 1)
        n = self.cur
        while n is not None and n.tag != tag:
            n = n.parent
        if n is not None and n.parent is not None:
            self.cur = n.parent

    def handle_data(self, data):
        if not self.skip:
            self.cur.kids.append(data)


def page_items():
    """What the search finds on the home page. Each item remembers the CSS selector `sel` and its position `n`
    among the matches, so the browser can find the element again (document.querySelectorAll(sel)[n])."""
    tree = Tree()
    tree.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    squash = lambda t: re.sub(r"\s+", " ", t).strip()
    sub = lambda n, c: n.first(c)

    def anc(n):
        n = n.parent
        while n is not None:
            yield n
            n = n.parent

    # (selector, matcher, section, title, is a link)
    sources = [
        (".hero-text", lambda n: n.has("hero-text"), "About", lambda n: "About Khairul Alam", False),
        (".stat-card", lambda n: n.has("stat-card"), "Highlights", lambda n: n.text(), False),
        (".exp-card", lambda n: n.has("exp-card"), "Experience", lambda n: sub(n, "exp-title").text(), False),
        (".st-group", lambda n: n.has("st-group"), "Skills", lambda n: sub(n, "st-name").text(), False),
        (".st-leaves .tag", lambda n: n.has("tag") and any(a.has("st-leaves") for a in anc(n)), "Skills", lambda n: n.text(), False),
        (".oss-card", lambda n: n.has("oss-card"), "Open Source", lambda n: sub(n, "oss-name").text(), False),
        (".series-card", lambda n: n.has("series-card"), "Writing", lambda n: sub(n, "series-title").text(), False),
        (".series-part", lambda n: n.has("series-part"), "Writing", lambda n: "Claude Code series, Part " + sub(n, "sp-num").text() + ": " + sub(n, "sp-title").text(), True),
        (".blog-card", lambda n: n.has("blog-card"), "Writing", lambda n: sub(n, "blog-title").text(), True),
        (".lead-item", lambda n: n.has("lead-item"), "Leadership", lambda n: n.first(tag="p").text(), False),
        (".edu-card", lambda n: n.has("edu-card"), "Education", lambda n: sub(n, "edu-degree").text(), False),
        (".interest-chip", lambda n: n.has("interest-chip"), "Interests", lambda n: sub(n, "interest-label").text(), False),
        (".view-all-link", lambda n: n.has("view-all-link"), "Writing", lambda n: n.text(), True),
    ]

    out = []
    for sel, match, section, title_fn, link in sources:
        pos = -1
        for n in tree.root.walk():
            if not match(n):
                continue
            pos += 1                                   # position among everything the selector matches
            try:
                title = squash(title_fn(n))
            except AttributeError:
                continue
            if not title:
                continue
            item = {"id": len(out), "title": title, "text": squash(n.text()), "section": section, "link": link,
                    "tag": n.has("tag"), "sel": sel, "n": pos}
            if link:
                href = n.attrs.get("href")
                if not href:
                    continue
                item["href"] = href
                item["ext"] = n.attrs.get("target") == "_blank"
            else:
                sec = next((a for a in anc(n) if a.tag == "section" and a.attrs.get("id")), None)
                item["href"] = "index.html" + ("#" + sec.attrs["id"] if sec else "")
                item["ext"] = False
            out.append(item)
    return out


def build_data_js(articles):
    d = ROOT / "data" / "search"
    d.mkdir(parents=True, exist_ok=True)
    page = page_items()
    payload = json.dumps({"articles": articles, "page": page}, ensure_ascii=False, separators=(",", ":"))
    (d / "search-data.js").write_text("window.SITE_SEARCH=" + payload + ";\n", encoding="utf-8")
    print(f"Wrote data/search/search-data.js: {len(articles)} articles, {len(page)} home page items")


def last_modified(path):
    """Date of the last commit that touched a file (YYYY-MM-DD), or None when git history is not available."""
    try:
        out = subprocess.run(["git", "log", "-1", "--format=%cs", "--", str(path.relative_to(ROOT))],
                             cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()
        return out or None
    except Exception:
        return None


def build_sitemap():
    pages = [(ROOT / "index.html", SITE)] + [(p, SITE + "blog/" + p.name) for p in sorted((ROOT / "blog").glob("*.html"))]
    rows = []
    for path, url in pages:
        mod = last_modified(path)
        rows.append("  <url><loc>%s</loc>%s</url>" % (url, "<lastmod>%s</lastmod>" % mod if mod else ""))
    xml = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + "\n".join(rows) + "\n</urlset>\n"
    (ROOT / "sitemap.xml").write_text(xml, encoding="utf-8")
    print(f"Wrote sitemap.xml: {len(pages)} pages")


if __name__ == "__main__":
    build()
    build_sitemap()
