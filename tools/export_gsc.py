# -*- coding: utf-8 -*-
"""GSCの記事別パフォーマンスを書き出す（日次改善ループ・順位履歴用）

- reports/gsc_latest.json: 直近7日/28日の記事別・クエリ別集計（改善routineが参照）
- reports/rank_history.csv: 日別×記事別の表示・クリック・順位の全履歴（ロング形式）
- reports/rank_matrix.csv: 日付×記事の平均順位マトリクス（スプレッドシート閲覧用）
"""
import csv
import datetime
import glob
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daily_report import gsc_token, SITE, DOMAIN

LAUNCH = '2026-09-18'  # サイト公開日（履歴の起点）

def query(token, start, end, dims, limit=500):
    url = f'https://searchconsole.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(SITE, safe="")}/searchAnalytics/query'
    body = json.dumps({'startDate': start, 'endDate': end, 'dimensions': dims, 'rowLimit': limit}).encode()
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as r:
        return json.load(r).get('rows', [])


def load_articles():
    """{path: (表示名, order)} を返す"""
    arts = {}
    for p in glob.glob('data/*.json'):
        d = json.load(open(p, encoding='utf-8'))
        if isinstance(d, dict) and 'slug' in d:
            name = d.get('city') or d.get('title_short') or d['slug']
            arts[f"/{d['slug']}/"] = (name, d.get('order', 999))
    return arts


def export_history(token, end):
    """日別×記事別の履歴CSVを全期間分再生成（常に整合する冪等方式）"""
    arts = load_articles()
    rows = query(token, LAUNCH, end, ['date', 'page'], limit=25000)
    hist = []
    for r in rows:
        date, page = r['keys'][0], r['keys'][1].replace(DOMAIN, '') or '/'
        hist.append((date, page, int(r['impressions']), int(r['clicks']),
                     round(r['position'], 1)))
    hist.sort()

    with open('reports/rank_history.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['date', 'page', 'name', 'impressions', 'clicks', 'position'])
        for date, page, imp, clk, pos in hist:
            name = arts.get(page, ('トップ' if page == '/' else page, 0))[0]
            w.writerow([date, page, name, imp, clk, pos])

    # 日付×記事の順位マトリクス（列は記事order順、表示実績のある記事のみ）
    dates = sorted({h[0] for h in hist})
    pages_seen = {h[1] for h in hist if h[1] in arts}
    cols = sorted(pages_seen, key=lambda p: arts[p][1])
    posmap = {(h[0], h[1]): h[4] for h in hist}
    with open('reports/rank_matrix.csv', 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['日付'] + [arts[c][0] for c in cols])
        for d in dates:
            w.writerow([d] + [posmap.get((d, c), '') for c in cols])
    return len(hist), len(dates), len(cols)

def main():
    token = gsc_token(os.environ['GSC_SA_KEY'])
    today = datetime.date.today()
    end = (today - datetime.timedelta(days=2)).isoformat()
    start7 = (today - datetime.timedelta(days=8)).isoformat()
    start28 = (today - datetime.timedelta(days=29)).isoformat()
    out = {
        'generated': today.isoformat(),
        'range7': [start7, end], 'range28': [start28, end],
        'pages_7d': [], 'pages_28d': [], 'queries_28d': [],
    }
    for key, (s, e, dims) in {
        'pages_7d': (start7, end, ['page']),
        'pages_28d': (start28, end, ['page']),
        'queries_28d': (start28, end, ['page', 'query']),
    }.items():
        for row in query(token, s, e, dims):
            item = {'keys': [k.replace(DOMAIN, '') or '/' for k in row['keys']],
                    'imp': int(row['impressions']), 'clicks': int(row['clicks']),
                    'pos': round(row['position'], 1)}
            out[key].append(item)
    os.makedirs('reports', exist_ok=True)
    with open('reports/gsc_latest.json', 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    n_rows, n_dates, n_pages = export_history(token, end)
    print(f"export OK: pages7={len(out['pages_7d'])} pages28={len(out['pages_28d'])} "
          f"queries={len(out['queries_28d'])} history={n_rows}行/{n_dates}日/{n_pages}記事")

if __name__ == '__main__':
    main()
