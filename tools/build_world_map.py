#!/usr/bin/env python3
"""Build llm-map.js: country outlines for the world map on the LLM models page.

This is a ONE-TIME step (the outlines never change), not part of the daily refresh.
Source: Natural Earth via the "world-atlas" package (public domain), 110m countries.

    python3 tools/build_world_map.py

Writes llm-map.js, which defines window.LLM_MAP = {w, h, countries: [{name, d, cx, cy}, ...]}.
Projection: Natural Earth (Savric 2015). Python standard library only.
"""
import json
import math
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
URL = "https://cdn.jsdelivr.net/npm/world-atlas@2/countries-110m.json"
WIDTH = 1000.0

# Countries too small for the 110m outlines get a marker only: name -> (latitude, longitude)
MARKER_ONLY = {"Singapore": (1.35, 103.82)}


def project(lon, lat):
    """Natural Earth projection (Savric 2015)."""
    l, p = math.radians(lon), math.radians(lat)
    p2, p4 = p * p, p ** 4
    x = l * (0.8707 - 0.131979 * p2 + p4 * (-0.013791 + p4 * (0.003971 * p2 - 0.001529 * p4)))
    y = p * (1.007226 + p2 * (0.015085 + p4 * (-0.044475 + 0.028874 * p2 - 0.005916 * p4)))
    return x, y


def decode(topo):
    sx, sy = topo["transform"]["scale"]
    tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    return arcs


def ring_points(ring, arcs):
    out = []
    for i in ring:
        pts = arcs[i] if i >= 0 else list(reversed(arcs[~i]))
        out.extend(pts if not out else pts[1:])
    return out


def unwrap(lonlat):
    """Make longitudes continuous across the antimeridian. Returns (points, crossed)."""
    out, crossed = [lonlat[0]], False
    for lon, lat in lonlat[1:]:
        prev = out[-1][0]
        while lon - prev > 180:
            lon -= 360
            crossed = True
        while lon - prev < -180:
            lon += 360
            crossed = True
        out.append((lon, lat))
    return out, crossed


def area(pts):
    return abs(sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1] for i in range(len(pts)))) / 2


def centroid(pts):
    a = 0.0
    cx = cy = 0.0
    for i in range(len(pts)):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % len(pts)]
        c = x0 * y1 - x1 * y0
        a += c
        cx += (x0 + x1) * c
        cy += (y0 + y1) * c
    if abs(a) < 1e-12:
        return pts[0]
    return cx / (3 * a), cy / (3 * a)


def main():
    req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0"})
    topo = json.load(urllib.request.urlopen(req, timeout=120))
    arcs = decode(topo)
    raw = []                                                    # (name, [rings of projected points])
    for g in topo["objects"]["countries"]["geometries"]:
        name = g["properties"]["name"]
        if name == "Antarctica":
            continue
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        rings = []
        for poly in polys:
            for ring in poly:
                ll, crossed = unwrap(ring_points(ring, arcs))
                rings.append([project(lon, lat) for lon, lat in ll])
                if crossed:                                     # also draw it shifted by one world width, so the
                    shift = -360 if max(lo for lo, _ in ll) > 180 else 360   # far side of the date line shows up on the other edge
                    rings.append([project(lon + shift, lat) for lon, lat in ll])
        raw.append((name, rings))

    ys = [y for _, rs in raw for r in rs for _, y in r if -5 < y < 5]            # placeholder, replaced below
    ys = [project(0, lat)[1] for lat in (-56, 84)]
    minx, maxx = project(-180, 0)[0], project(180, 0)[0]
    miny, maxy = min(ys), max(ys)
    k = WIDTH / (maxx - minx)
    height = round((maxy - miny) * k, 1)

    def tf(p):
        return round((p[0] - minx) * k, 1), round((maxy - p[1]) * k, 1)    # flip y for SVG

    countries = []
    for name, rings in raw:
        d = []
        for r in rings:
            pts = [tf(p) for p in r]
            # drop points that round to the previous one
            slim = [pts[0]] + [p for i, p in enumerate(pts[1:], 1) if p != pts[i - 1]]
            if len(slim) < 3:
                continue
            d.append("M" + "L".join(f"{x:g},{y:g}" for x, y in slim) + "Z")
        biggest = max(rings, key=area)                                 # place the marker on the largest landmass
        cx, cy = tf(centroid(biggest))
        countries.append({"name": name, "d": "".join(d), "cx": cx, "cy": cy})
    for name, (lat, lon) in MARKER_ONLY.items():
        cx, cy = tf(project(lon, lat))
        countries.append({"name": name, "d": "", "cx": cx, "cy": cy})

    doc = {"w": WIDTH, "h": height, "countries": countries}
    out = ROOT / "llm-map.js"
    out.write_text("window.LLM_MAP=" + json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + ";\n", encoding="utf-8")
    print(f"Wrote {out.name}: {len(countries)} countries, {out.stat().st_size / 1024:.0f} KB, viewBox 0 0 {WIDTH:g} {height}")


if __name__ == "__main__":
    main()
