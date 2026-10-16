# -*- coding: utf-8 -*-
"""SERP定点観測: スナップショットの差分検知とベンチマーク出力

使い方:
    python3 tools/serp_diff.py <today_snapshot.json>

入力（当日スナップショット）の形式:
    {"date": "YYYY-MM-DD",
     "results": {"<query>": [{"rank": 1, "url": "...", "title": "..."}, ...]}}

処理:
- reports/serp_history.json に当日分を追記（同日再実行は上書き、直近90日分保持）
- 前回スナップショットおよび直近14回の履歴と比較してアラートを標準出力に出す:
  * NEW_DOMAIN: 直近14回に一度も出ていないドメインがトップ10に入った
  * RISER: 同一URLが前回比4位以上ジャンプ、または圏外からトップ5入り
  * LOST: 自社記事(amamori-reform.com)がトップ10から消えた
- reports/serp_benchmark.csv を全履歴から再生成（冪等）:
  日付,クエリ,自社順位,1位ドメイン,2位ドメイン,3位ドメイン
  → スプレッドシートにIMPORTDATAで取り込み、競合との差を時系列で追う

検索結果の順序は近似値のため、±2程度の変動はノイズとして扱うこと。
"""
import csv
import json
import os
import sys
from urllib.parse import urlparse

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HIST = os.path.join(BASE, 'reports', 'serp_history.json')
BENCH = os.path.join(BASE, 'reports', 'serp_benchmark.csv')
OWN = 'amamori-reform.com'
LOOKBACK = 14   # NEW_DOMAIN判定に使う履歴数
KEEP = 90       # 保持するスナップショット数


def domain(url):
    d = urlparse(url).netloc.lower()
    return d[4:] if d.startswith('www.') else d


def load_history():
    if not os.path.exists(HIST):
        return []
    return json.load(open(HIST, encoding='utf-8'))


def detect(today, history):
    """アラート行のリストを返す"""
    alerts = []
    prev = history[-1] if history else None
    recent = history[-LOOKBACK:]
    for query, rows in today['results'].items():
        prev_rows = (prev or {}).get('results', {}).get(query, [])
        prev_rank = {r['url']: r['rank'] for r in prev_rows}
        seen_domains = {domain(r['url'])
                        for snap in recent
                        for r in snap.get('results', {}).get(query, [])}
        for r in rows:
            d = domain(r['url'])
            if d == OWN:
                continue
            if seen_domains and d not in seen_domains:
                alerts.append(f"NEW_DOMAIN [{query}] {r['rank']}位 {d} {r['url']} 「{r.get('title','')}」")
            elif r['url'] in prev_rank and prev_rank[r['url']] - r['rank'] >= 4:
                alerts.append(f"RISER [{query}] {prev_rank[r['url']]}位→{r['rank']}位 {r['url']}")
            elif prev_rows and r['url'] not in prev_rank and r['rank'] <= 5:
                alerts.append(f"RISER [{query}] 圏外→{r['rank']}位 {r['url']}")
        own_now = any(domain(r['url']) == OWN for r in rows)
        own_before = any(domain(r['url']) == OWN for r in prev_rows)
        if own_before and not own_now:
            alerts.append(f"LOST [{query}] 自社記事がトップ10圏外に落ちた")
    return alerts


def write_benchmark(history):
    """全履歴からベンチマークCSVを冪等再生成"""
    with open(BENCH, 'w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['日付', 'クエリ', '自社順位', '1位', '2位', '3位'])
        for snap in history:
            for query, rows in sorted(snap.get('results', {}).items()):
                own = next((r['rank'] for r in rows if domain(r['url']) == OWN), '')
                top3 = [domain(r['url']) for r in sorted(rows, key=lambda r: r['rank'])[:3]]
                top3 += [''] * (3 - len(top3))
                w.writerow([snap['date'], query, own] + top3)


def main():
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    today = json.load(open(sys.argv[1], encoding='utf-8'))
    if 'date' not in today or 'results' not in today:
        sys.exit('スナップショット形式が不正です（date/resultsが必要）')

    history = [s for s in load_history() if s['date'] != today['date']]
    alerts = detect(today, history)
    history = (history + [today])[-KEEP:]

    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    with open(HIST, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=1)
    write_benchmark(history)

    if alerts:
        print(f'=== アラート {len(alerts)}件 ===')
        for a in alerts:
            print(a)
    else:
        print('アラートなし（初回実行時は比較対象がないためアラートは出ません）')
    print(f'history: {len(history)}日分 / benchmark: reports/serp_benchmark.csv 更新')


if __name__ == '__main__':
    main()
