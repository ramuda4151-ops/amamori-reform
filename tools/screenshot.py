# -*- coding: utf-8 -*-
"""業者公式サイトのスクリーンショットをヘッドレスで撮影する

使い方:
    python3 tools/screenshot.py <出力名>=<URL> [<出力名>=<URL> ...]
    例: python3 tools/screenshot.py site_example=https://example.com/

優先: Playwright + Chromium（初回のみ: pip install playwright && playwright install chromium。
      クラウド実行環境ではプリインストールのブラウザに合わせ pip install playwright==1.56.0）
代替: ChromiumがTLS再終端プロキシ等でサイトに到達できない環境では、
      WordPress mShots API（サーバーサイドスクショ）に自動フォールバックする。
出力: img/<出力名>.jpg（幅800px・ファーストビュー）
"""
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
IMG = BASE / 'img'


def shot_mshots(name: str, url: str) -> bool:
    """mShots APIでスクショ取得（生成完了までポーリング）"""
    api = ('https://s0.wp.com/mshots/v1/' + urllib.parse.quote(url, safe='')
           + '?w=800&vpw=1280&vph=800')  # 既存スクショと同じデスクトップ幅ビューポート
    out = IMG / f'{name}.jpg'
    for _ in range(24):  # 新規URLは生成に1〜3分かかることがある
        req = urllib.request.Request(api, headers={'User-Agent': 'Mozilla/5.0'})
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                ctype = r.headers.get('Content-Type', '')
                data = r.read()
        except Exception as e:
            print(f'  mshots取得エラー({name}): {e}')
            time.sleep(8)
            continue
        # 生成中はローディングGIFが返る。JPEGになったら完成
        if 'jpeg' in ctype and len(data) > 10000:
            out.write_bytes(data)
            print(f'  OK(mshots): {out.name} <- {url}')
            return True
        time.sleep(8)
    print(f'  NG(mshots): {name} ({url}): 生成が完了しませんでした')
    return False


def shot_playwright(page, name: str, url: str) -> bool:
    out = IMG / f'{name}.jpg'
    page.goto(url, wait_until='load', timeout=45000)
    time.sleep(3)  # 遅延描画・ヒーローアニメーション待ち
    page.screenshot(path=str(out), type='jpeg', quality=80)
    # 幅800pxへ縮小（macOSはsips、無ければPlaywright解像度のまま）
    try:
        subprocess.run(['sips', '--resampleWidth', '800', str(out)],
                       capture_output=True)
    except FileNotFoundError:
        pass
    print(f'  OK: {out.name} <- {url}')
    return True


def main() -> None:
    jobs = []
    for arg in sys.argv[1:]:
        name, _, url = arg.partition('=')
        if not url:
            sys.exit(f'引数の形式が不正: {arg}（<出力名>=<URL>）')
        jobs.append((name, url))
    if not jobs:
        sys.exit('引数がありません')

    pending = list(jobs)
    try:
        from playwright.sync_api import sync_playwright
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page(viewport={'width': 1280, 'height': 800},
                                    device_scale_factor=1.25)
            remain = []
            for name, url in pending:
                try:
                    shot_playwright(page, name, url)
                except Exception as e:
                    print(f'  Playwright失敗: {name} ({url}): {e}')
                    remain.append((name, url))
            browser.close()
            pending = remain
    except Exception as e:
        print(f'Playwright利用不可（mShotsへフォールバック）: {e}')

    failed = [j for j in pending if not shot_mshots(*j)]
    if failed:
        sys.exit(f'撮影失敗: {", ".join(n for n, _ in failed)}')


if __name__ == '__main__':
    main()
