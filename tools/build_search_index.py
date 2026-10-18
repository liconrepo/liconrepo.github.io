#!/usr/bin/env python3
"""Build search-index.json: the full text of every article in blog/, split at headings.

Run from the repository root after adding or editing a post:

    python3 tools/build_search_index.py

The home page loads search-index.json the first time the search box is opened,
so searching finds words anywhere inside the articles, not just in their titles.
"""
import json, re, sys
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
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
    (ROOT / "search-index.json").write_text(json.dumps(out, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    size = (ROOT / "search-index.json").stat().st_size
    print(f"\nWrote search-index.json: {len(out)} articles, {size/1024:.0f} KB")


if __name__ == "__main__":
    build()
