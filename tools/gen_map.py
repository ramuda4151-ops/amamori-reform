# -*- coding: utf-8 -*-
"""都道府県シルエット＋市の位置ピンのSVG地図を img/map_<slug>.svg に生成する

使い方:
    python3 tools/gen_map.py                       # data/*.json の全市を再生成
    python3 tools/gen_map.py <slug> <市名> <都道府県>  # 1市だけ生成（新市追加時）
"""
import glob
import json
import math
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GEO = json.load(open(f'{BASE}/tools/japan.geojson'))

# 市庁舎付近の座標 (lon, lat)
CITY_COORDS = {
    'machida': (139.4387, 35.5466), 'sagamihara': (139.3542, 35.5711),
    'yokohama': (139.6380, 35.4437), 'kawasaki': (139.7029, 35.5308),
    'fujisawa': (139.4633, 35.3390), 'yokosuka': (139.6720, 35.2815),
    'saitama': (139.6455, 35.8617), 'chiba': (140.1063, 35.6073),
    'funabashi': (139.9825, 35.6947), 'hachioji': (139.3159, 35.6664),
    'sendai': (140.8694, 38.2682),
    'kawaguchi': (139.7241, 35.8078), 'kashiwa': (139.9698, 35.8676),
    'matsudo': (139.9030, 35.7876), 'kawagoe': (139.4857, 35.9251),
    'koriyama': (140.3598, 37.4004), 'tokorozawa': (139.4687, 35.7996),
    'koshigaya': (139.7908, 35.8911), 'hiratsuka': (139.3498, 35.3354),
    'chigasaki': (139.4047, 35.3339), 'iwaki': (140.8877, 37.0505),
    'atsugi': (139.3625, 35.4433), 'yamato': (139.4580, 35.4874),
    'fuchu': (139.4777, 35.6690), 'chofu': (139.5407, 35.6506),
    'fukushima': (140.4747, 37.7608), 'utsunomiya': (139.8836, 36.5551),
    'takasaki': (139.0032, 36.3219), 'mito': (140.4467, 36.3659),
    'tsukuba': (140.0763, 36.0835), 'aomori': (140.7406, 40.8222),
    'hachinohe': (141.4883, 40.5124), 'morioka': (141.1527, 39.7036),
    'akita': (140.1025, 39.7200), 'yamagata': (140.3633, 38.2554),
    'ishinomaki': (141.3028, 38.4344),
}

W, H, PAD = 740, 420, 46


def ring_area(ring):
    s = 0.0
    for i in range(len(ring) - 1):
        s += ring[i][0] * ring[i + 1][1] - ring[i + 1][0] * ring[i][1]
    return abs(s) / 2


def centroid(ring):
    xs = [p[0] for p in ring]
    ys = [p[1] for p in ring]
    return sum(xs) / len(xs), sum(ys) / len(ys)


def main_polygons(feature):
    """本土のみ返す（最大ポリゴンの重心から0.6度以上離れた島嶼は除外）"""
    g = feature['geometry']
    polys = [g['coordinates']] if g['type'] == 'Polygon' else g['coordinates']
    areas = [ring_area(p[0]) for p in polys]
    amax = max(areas)
    cx0, cy0 = centroid(polys[areas.index(amax)][0])
    out = []
    for p, a in zip(polys, areas):
        cx, cy = centroid(p[0])
        if a >= amax / 50 and abs(cx - cx0) < 0.6 and abs(cy - cy0) < 0.6:
            out.append(p)
    return out


def render(slug, city, pref):
    feat = next(f for f in GEO['features'] if f['properties']['nam_ja'] == pref)
    polys = main_polygons(feat)
    lons = [pt[0] for p in polys for pt in p[0]]
    lats = [pt[1] for p in polys for pt in p[0]]
    minlon, maxlon, minlat, maxlat = min(lons), max(lons), min(lats), max(lats)
    klon = math.cos(math.radians((minlat + maxlat) / 2))
    spanx, spany = (maxlon - minlon) * klon, (maxlat - minlat)
    scale = min((W - PAD * 2) / spanx, (H - PAD * 2) / spany)
    offx = (W - spanx * scale) / 2
    offy = (H - spany * scale) / 2

    def xy(lon, lat):
        return ((lon - minlon) * klon * scale + offx, (maxlat - lat) * scale + offy)

    paths = []
    for p in polys:
        pts = [xy(lon, lat) for lon, lat in p[0]]
        dstr = 'M' + ' L'.join(f'{x:.1f} {y:.1f}' for x, y in pts) + ' Z'
        paths.append(dstr)

    cx, cy = xy(*CITY_COORDS[slug])
    lx = cx + 22
    anchor = 'start'
    if lx + len(city) * 30 > W - 12:
        lx = cx - 22
        anchor = 'end'
    ly = min(max(cy + 10, 44), H - 16)

    path_els = '\n  '.join(
        f'<path d="{d}" fill="#d9ebe7" stroke="#17756d" stroke-width="2.5" stroke-linejoin="round"/>'
        for d in paths)
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" font-family="'Zen Maru Gothic','Hiragino Kaku Gothic ProN',sans-serif">
  <rect width="{W}" height="{H}" fill="#f2f8f6"/>
  {path_els}
  <text x="24" y="42" font-size="24" font-weight="700" fill="#7c9b96">{pref}</text>
  <circle cx="{cx:.1f}" cy="{cy:.1f}" r="26" fill="#ee7b2e" opacity="0.18"/>
  <path d="M{cx:.1f} {cy - 30:.1f} C{cx - 13:.1f} {cy - 30:.1f} {cx - 16:.1f} {cy - 16:.1f} {cx:.1f} {cy:.1f} C{cx + 16:.1f} {cy - 16:.1f} {cx + 13:.1f} {cy - 30:.1f} {cx:.1f} {cy - 30:.1f} Z" fill="#ee7b2e"/>
  <circle cx="{cx:.1f}" cy="{cy - 21:.1f}" r="6.5" fill="#ffffff"/>
  <text x="{lx:.1f}" y="{ly:.1f}" font-size="32" font-weight="700" fill="#17756d" stroke="#ffffff" stroke-width="7" paint-order="stroke" text-anchor="{anchor}">{city}</text>
</svg>
'''
    with open(f'{BASE}/img/map_{slug}.svg', 'w', encoding='utf-8') as f:
        f.write(svg)
    return len(svg)


if __name__ == '__main__':
    if len(sys.argv) == 4:
        slug, city, pref = sys.argv[1], sys.argv[2], sys.argv[3]
        print(f'map_{slug}.svg ({render(slug, city, pref)}B)')
        sys.exit()
    for p in sorted(glob.glob(f'{BASE}/data/*.json')):
        d = json.load(open(p, encoding='utf-8'))
        if not isinstance(d, dict) or 'slug' not in d:
            continue
        if d['slug'] not in CITY_COORDS:
            print('SKIP (座標なし):', d['slug'])
            continue
        print(f"map_{d['slug']}.svg ({render(d['slug'], d['city'], d['pref'])}B)")
