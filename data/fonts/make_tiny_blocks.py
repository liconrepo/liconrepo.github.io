"""Build Tiny Blocks, a six-letter demo font, from code.

    pip install fonttools
    python3 make_tiny_blocks.py        # writes TinyBlocks-Regular.ttf next to this file

Every letter is a polygon of straight lines on a 1000-unit grid. Outer shapes run clockwise
(the TrueType convention); counters (the hole in the O) run the other way.
"""
from pathlib import Path
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.ttGlyphPen import TTGlyphPen

UPM, ASC, DESC = 1000, 800, -200            # units per em, ascender, descender


def glyph(*contours):
    pen = TTGlyphPen(None)
    for pts in contours:
        pen.moveTo(pts[0])
        for p in pts[1:]:
            pen.lineTo(p)
        pen.closePath()
    return pen.glyph()


SHAPES = {                                   # name: (advance width, contours)
    ".notdef": (500, [[(60, 0), (60, 700), (440, 700), (440, 0)], [(140, 80), (360, 80), (360, 620), (140, 620)]]),
    "space": (300, []),
    "I": (400, [[(130, 0), (130, 700), (270, 700), (270, 0)]]),
    "L": (600, [[(80, 0), (80, 700), (220, 700), (220, 140), (520, 140), (520, 0)]]),
    "T": (600, [[(40, 700), (560, 700), (560, 560), (370, 560), (370, 0), (230, 0), (230, 560), (40, 560)]]),
    "H": (600, [[(80, 0), (80, 700), (220, 700), (220, 420), (380, 420), (380, 700), (520, 700), (520, 0), (380, 0), (380, 280), (220, 280), (220, 0)]]),
    "E": (600, [[(80, 0), (80, 700), (520, 700), (520, 560), (220, 560), (220, 420), (480, 420), (480, 280), (220, 280), (220, 140), (520, 140), (520, 0)]]),
    "O": (600, [[(80, 0), (80, 700), (520, 700), (520, 0)], [(220, 140), (380, 140), (380, 560), (220, 560)]]),
}
CMAP = {0x20: "space", ord("I"): "I", ord("L"): "L", ord("T"): "T", ord("H"): "H", ord("E"): "E", ord("O"): "O"}

order = list(SHAPES)
glyphs = {n: glyph(*c) for n, (_, c) in SHAPES.items()}
metrics = {n: (adv, min(x for pts in c for x, _ in pts) if c else 0) for n, (adv, c) in SHAPES.items()}   # (advance width, left side bearing)

fb = FontBuilder(UPM, isTTF=True)
fb.setupGlyphOrder(order)
fb.setupCharacterMap(CMAP)
fb.setupGlyf(glyphs)
fb.setupHorizontalMetrics(metrics)
fb.setupHorizontalHeader(ascent=ASC, descent=DESC)
fb.setupNameTable({"familyName": "Tiny Blocks", "styleName": "Regular", "version": "Version 1.0"})
fb.setupOS2(sTypoAscender=ASC, sTypoDescender=DESC, sTypoLineGap=0, usWinAscent=ASC, usWinDescent=-DESC, sCapHeight=700, sxHeight=700)
fb.setupPost()
out = Path(__file__).with_name("TinyBlocks-Regular.ttf")
fb.save(str(out))
print("wrote", out, out.stat().st_size, "bytes")
