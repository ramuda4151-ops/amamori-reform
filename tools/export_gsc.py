# -*- coding: utf-8 -*-
"""GSCの記事別パフォーマンスを reports/gsc_latest.json に書き出す（週次改善ループ用）"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from daily_report import gsc_token, SITE, DOMAIN

def query(token, start, end, dims):
    url = f'https://searchconsole.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(SITE, safe="")}/searchAnalytics/query'
    body = json.dumps({'startDate': start, 'endDate': end, 'dimensions': dims, 'rowLimit': 500}).encode()
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as r:
        return json.load(r).get('rows', [])

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
    print(f"export OK: pages7={len(out['pages_7d'])} pages28={len(out['pages_28d'])} queries={len(out['queries_28d'])}")

if __name__ == '__main__':
    main()
