# -*- coding: utf-8 -*-
"""矢量物流地图（M4-SERVICE / P.05 服务与物流）。

**为什么是矢量**：已批准基线（MARS-12 评论 `01a0f106`）该页位图数仍是 2
（只有右栏两个品牌 logo），地图本身是**矢量描线**——贴一张地图位图会直接
破坏这条逐页判据，也会在印刷版上丢掉边缘锐度。

数据：`assets/geo/countries-110m.json`（world-atlas TopoJSON / Natural Earth
110m，177 个国家、286 个环）。

投影：与已批准基线**逐点对齐**的等距圆柱（equirectangular）：
    x_mm = K_LON · 经度 + X0
    y_mm = Y_LAT0 − K_LAT · 纬度
**纬度是线性的，不是 Mercator**：基线 4 个航点（Rotterdam / Tokyo /
Los Angeles / 上海，纬度 31–52°N）在两种模型下都在 0.13mm 内，但用
海南岛（19.15°N）与福克兰群岛（−51.7°S）当检验点时，Mercator 差 1.2mm、
线性模型仍在 0.2mm 内 —— 故取线性（`fit_map3.py` 的掩膜 IoU 也印证：
线性 0.76 vs Mercator 0.28，1px 膨胀后）。
经度跨度按整 360° 取（大西洋 30°W 断口），与 D1 设计件 desc 的
"Atlantic 30W break" 一致。

叠层元素（国界、China 高亮、航线、航点、地名、图例）的锚点/控制点均取
**已批准基线实测值**——原实现的代码随故障机丢失，这里按实测逐点还原，
不重新"设计"一版地图。
"""
import json
import os

from reportlab.lib.units import mm

from . import tokens as T

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
GEO_PATH = os.path.join(ROOT, "assets", "geo", "countries-110m.json")

# ---------------------------------------------------------------- 投影
K_LON = 0.3332        # mm / 经度（基线反解）
X0 = 124.14           # 经度 0 → x（mm）
K_LAT = 0.4344        # mm / 纬度（线性纬度，非 Mercator）
Y_LAT0 = 70.70        # 纬度 0（赤道）→ y（自页顶向下，mm）
LON_BREAK = -30.4     # 大西洋断口：经度 < 此值的几何 +360° 折到右侧

# 地图可视框（= 基线实测裁切框：上/下缘都被几何切断）
BOX = (114.0, 34.15, 234.2, 94.96)

# ---------------------------------------------------------------- 叠层
# 目的港：名称 + 经纬度 + 地名锚点（墨迹左沿 x、墨迹上沿 y，mm，基线实测）
DEST_PORTS = [
    ("Rotterdam", 4.48, 51.92, (127.43, 48.58)),
    ("Tokyo", 139.69, 35.69, (172.37, 55.18)),
    ("Los Angeles", -118.24, 34.05, (206.40, 55.89)),
]
# 起运地（宁波/上海一体，基线标记实测反解经度 121.10、纬度 31.00）
ORIGIN_PORT = (121.10, 31.00)
CHINA_LABEL = ("CHINA", 149.50, 60.22)      # 地标文字锚点（基线实测）

# 三条航线：三次贝塞尔 [p0, c1, c2, p3]（mm，自页顶向下；基线实测控制点）
LANES = [
    [(158.70, 54.70), (150.43, 46.36), (133.90, 43.02), (125.63, 48.02)],
    [(164.50, 57.05), (166.02, 51.07), (169.05, 50.09), (170.57, 55.09)],
    [(164.50, 57.05), (174.52, 51.42), (194.58, 50.79), (204.60, 55.79)],
]
LANE_W = 0.55          # mm（基线 1.559pt）
CHINA_W = 0.30         # mm（基线 0.85pt）
R_DEST = 0.90          # mm（基线 5.1pt 直径）
R_ORIGIN = 1.30        # mm（基线 7.4pt 直径）

LEGEND_LINE_Y = 98.37                        # 图例细线 y（基线实测）
LEGEND_ANCHOR = (113.80, 98.87)              # 图例文字墨迹左上（基线实测）
LEGEND = "LANES NINGBO/SHANGHAI TO ROTTERDAM · TOKYO · LOS ANGELES"
LABEL_SIZE = 6.5

# 环间经度跳变超过该值即断开（跨断口的大圆环不画成横贯线）
_SPLIT_MM = 30.0

_cache = {}


def project(lon, lat):
    """经纬度 → (x, y)（mm，自页顶向下）。等距圆柱：纬度线性。"""
    if lon < LON_BREAK:
        lon += 360.0
    return K_LON * lon + X0, Y_LAT0 - K_LAT * lat


def countries():
    """[(国家名, [环, ...]), ...]；环 = [(经度, 纬度), ...]。"""
    if "c" in _cache:
        return _cache["c"]
    with open(GEO_PATH, encoding="utf-8") as f:
        topo = json.load(f)
    tr = topo["transform"]
    sx, sy = tr["scale"]
    tx, ty = tr["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0.0
        pts = []
        for dx, dy in arc:
            x += dx
            y += dy
            pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)

    def ring(idxs):
        pts = []
        for i in idxs:
            a = arcs[i] if i >= 0 else arcs[~i][::-1]
            pts.extend(a if not pts else a[1:])
        return pts

    out = []
    for g in topo["objects"]["countries"]["geometries"]:
        polys = g["arcs"] if g["type"] == "MultiPolygon" else [g["arcs"]]
        rings = [ring(r) for poly in polys for r in poly]
        out.append((g["properties"]["name"], rings))
    _cache["c"] = out
    return out


def _runs(ring_pts):
    """投影一个环，并按断口切成若干折线段（避免横贯地图的假线）。"""
    out, cur, last = [], [], None
    for lon, lat in ring_pts:
        x, y = project(lon, lat)
        if last is not None and abs(x - last) > _SPLIT_MM:
            if len(cur) > 1:
                out.append(cur)
            cur = []
        cur.append((x, y))
        last = x
    if len(cur) > 1:
        out.append(cur)
    return out


def _path(page, pts, close=False):
    c = page.c
    p = c.beginPath()
    p.moveTo(page.X(pts[0][0]), page.Y(pts[0][1]))
    for x, y in pts[1:]:
        p.lineTo(page.X(x), page.Y(y))
    if close:
        p.close()
    return p


def _draw_countries(page):
    c = page.c
    c.setStrokeColorRGB(*T.rgb(T.HAIR))
    c.setLineWidth(T.HAIR_W * mm)
    c.setLineJoin(0)
    c.setLineCap(0)
    n = 0
    for name, rings in countries():
        for r in rings:
            for seg in _runs(r):
                c.drawPath(_path(page, seg), stroke=1, fill=0)
                n += 1
    return n


def _draw_china(page):
    c = page.c
    c.setStrokeColorRGB(*T.rgb(T.ACCENT))
    c.setFillColorRGB(*T.rgb(T.MAP_LAND_FILL))
    c.setLineWidth(CHINA_W * mm)
    c.setLineJoin(0)
    n = 0
    for name, rings in countries():
        if name != "China":
            continue
        for r in rings:
            segs = _runs(r)
            if not segs:
                continue
            pts = [p for seg in segs for p in seg]
            c.drawPath(_path(page, pts, close=True), stroke=1, fill=1)
            n += 1
    return n


def _draw_lanes(page):
    c = page.c
    c.setStrokeColorRGB(*T.rgb(T.ACCENT))
    c.setLineWidth(LANE_W * mm)
    c.setLineCap(1)
    for p0, c1, c2, p3 in LANES:
        p = c.beginPath()
        p.moveTo(page.X(p0[0]), page.Y(p0[1]))
        p.curveTo(page.X(c1[0]), page.Y(c1[1]),
                  page.X(c2[0]), page.Y(c2[1]),
                  page.X(p3[0]), page.Y(p3[1]))
        c.drawPath(p, stroke=1, fill=0)


def _dot(page, x, y, r):
    c = page.c
    c.circle(page.X(x), page.Y(y), r * mm, stroke=0, fill=1)


def _draw_ports(page):
    c = page.c
    c.setFillColorRGB(*T.rgb(T.ACCENT))
    ox, oy = project(*ORIGIN_PORT)
    for _name, lon, lat, _anchor in DEST_PORTS:
        x, y = project(lon, lat)
        _dot(page, x, y, R_DEST)
    _dot(page, ox, oy, R_ORIGIN)


def _text(page, anchor, s, color):
    """按墨迹左上锚点落字（锚点取基线实测，故用墨迹上沿换算墨迹下沿）。"""
    from .base import F_LATIN_MED
    from .textmetrics import ink_mm
    x_ink_left, y_ink_top = anchor
    m = ink_mm(F_LATIN_MED, LABEL_SIZE, s, T.TRACK_LABEL)
    h = (m["above"] + m["below"]) if m else 1.66
    page.text_inkleft(x_ink_left, y_ink_top + h, s, F_LATIN_MED, LABEL_SIZE,
                      color, T.TRACK_LABEL)


def _draw_labels(page):
    for name, _lon, _lat, anchor in DEST_PORTS:
        _text(page, anchor, name, T.INK)
    _text(page, (CHINA_LABEL[1], CHINA_LABEL[2]), CHINA_LABEL[0], T.INK)


def _draw_legend(page):
    x0, _y0, x1, _y1 = BOX
    page.hairline_top(x0, LEGEND_LINE_Y, x1 - x0)
    _text(page, LEGEND_ANCHOR, LEGEND, T.MUTED)


def draw(page):
    """把地图画进 P.05 内容区（几何裁剪在 BOX 内），返回构建 notes。"""
    x0, y0, x1, y1 = BOX
    c = page.c
    c.saveState()
    clip = c.beginPath()
    clip.rect(page.X(x0), page.Y(y1), (x1 - x0) * mm, (y1 - y0) * mm)
    c.clipPath(clip, stroke=0, fill=0)
    n = _draw_countries(page)
    _draw_china(page)
    _draw_lanes(page)
    _draw_ports(page)
    c.restoreState()
    _draw_labels(page)
    _draw_legend(page)
    return (f"物流地图：矢量描线 {n} 段（Natural Earth 110m）＋ "
            f"China 高亮＋3 条航线＋4 航点；裁剪框 x {x0}–{x1} / y {y0}–{y1}mm")