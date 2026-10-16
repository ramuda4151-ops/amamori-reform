# -*- coding: utf-8 -*-
"""SERP定点観測: スナップショットの差分検知とベンチマーク出力

使い方:
    python3 tools/serp_diff.py <today_snapshot.json>

入力（当日スナップショット）の形式:
    {"date": "YYYY-MM-DD",
     "results": {"<query>": [{"rank": 1, "url": "...", "title": "..."}, ...]}}

処理:
- reports/serp_history.json に当日分を追記（同日再実行は上書き、直近90日分保持）
- 履歴と比較してアラートを標準出力に出す。**単発の出現はたまたまの可能性があるため、
  連続して観測されたものだけを「確定」とする**（ユーザー指示 2026-10-16）:
  * NEW_DOMAIN確定: 過去14回に出ていなかったドメインが3回連続でトップ10に定着
  * RISER確定: 過去に圏外または下位だったURLが3回連続でトップ5に定着
  * LOST確定: 自社記事(amamori-reform.com)が2回連続でトップ10圏外
  * 上記の連続回数に達していないものは「経過観察」として表示のみ（分析・対応は不要）
  * 確定アラートは達成した当日だけ出す（毎日繰り返さない）
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
LOOKBACK = 14   # 「過去に居なかった」判定に使う履歴数
CONFIRM = 3     # 新規参入・急上昇の確定に必要な連続観測回数
CONFIRM_LOST = 2  # 自社圏外落ちの確定に必要な連続観測回数
KEEP = 90       # 保持するスナップショット数


def domain(url):
    d = urlparse(url).netloc.lower()
    return d[4:] if d.startswith('www.') else d


def load_history():
    if not os.path.exists(HIST):
        return []
    return json.load(open(HIST, encoding='utf-8'))


def streak_len(presence):
    """presence(古→新の bool 列)の末尾からの連続True数"""
    n = 0
    for p in reversed(presence):
        if not p:
            break
        n += 1
    return n


def detect(today, history):
    """確定アラートと経過観察の行リストを (confirmed, watching) で返す

    単発の出現はたまたまの可能性があるため、CONFIRM回連続で観測されたものだけ
    確定とし、確定した当日だけアラートを出す（毎日の重複出力はしない）。
    """
    confirmed, watching = [], []
    snaps = history + [today]  # 古→新
    for query, rows in today['results'].items():
        q_rows = [s.get('results', {}).get(query, []) for s in snaps]
        top10_domains = [{domain(r['url']) for r in rs} for rs in q_rows]
        top5_urls = [{r['url'] for r in rs if r['rank'] <= 5} for rs in q_rows]

        for r in rows:
            d = domain(r['url'])
            if d == OWN:
                continue
            # NEW_DOMAIN: 連続出現の開始前LOOKBACK回に居なかったドメイン
            st = streak_len([d in s for s in top10_domains])
            before = top10_domains[max(0, len(top10_domains) - st - LOOKBACK):len(top10_domains) - st]
            is_new = before and not any(d in s for s in before)
            if is_new:
                label = f"[{query}] {r['rank']}位 {d} {r['url']} 「{r.get('title', '')}」"
                if st == CONFIRM:
                    confirmed.append(f"NEW_DOMAIN確定({st}回連続) {label}")
                elif st < CONFIRM:
                    watching.append(f"経過観察 新規候補({st}回目) {label}")
            # RISER: トップ5に定着し、定着前LOOKBACK回はトップ5圏外だったURL
            if r['rank'] <= 5:
                st5 = streak_len([r['url'] in s for s in top5_urls])
                before5 = top5_urls[max(0, len(top5_urls) - st5 - LOOKBACK):len(top5_urls) - st5]
                was_out = before5 and not any(r['url'] in s for s in before5)
                if was_out and not is_new:  # NEW_DOMAINと二重報告しない
                    label = f"[{query}] {r['rank']}位 {r['url']}"
                    if st5 == CONFIRM:
                        confirmed.append(f"RISER確定({st5}回連続トップ5) {label}")
                    elif st5 < CONFIRM:
                        watching.append(f"経過観察 急上昇候補({st5}回目) {label}")

        # LOST: 自社がCONFIRM_LOST回連続で圏外（それ以前は居た）
        own_absent = [OWN not in s for s in top10_domains]
        st_lost = streak_len(own_absent)
        had_own = any(not a for a in own_absent[:len(own_absent) - st_lost])
        if had_own:
            if st_lost == CONFIRM_LOST:
                confirmed.append(f"LOST確定({st_lost}回連続圏外) [{query}] 自社記事がトップ10から消えた")
            elif 0 < st_lost < CONFIRM_LOST:
                watching.append(f"経過観察 自社圏外({st_lost}回目) [{query}]")
    return confirmed, watching


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
    confirmed, watching = detect(today, history)
    history = (history + [today])[-KEEP:]

    os.makedirs(os.path.dirname(HIST), exist_ok=True)
    with open(HIST, 'w', encoding='utf-8') as f:
        json.dump(history, f, ensure_ascii=False, indent=1)
    write_benchmark(history)

    if confirmed:
        print(f'=== 確定アラート {len(confirmed)}件（分析対象）===')
        for a in confirmed:
            print(a)
    else:
        print('確定アラートなし')
    if watching:
        print(f'--- 経過観察 {len(watching)}件（記録のみ・分析不要。連続{CONFIRM}回で確定）---')
        for a in watching:
            print(a)
    print(f'history: {len(history)}日分 / benchmark: reports/serp_benchmark.csv 更新')


if __name__ == '__main__':
    main()
