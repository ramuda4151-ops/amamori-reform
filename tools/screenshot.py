# -*- coding: utf-8 -*-
"""業者公式サイトのスクリーンショットをヘッドレスで撮影する

使い方:
    uv run --with playwright python3 tools/screenshot.py <出力名>=<URL> [<出力名>=<URL> ...]
    例: python3 tools/screenshot.py site_example=https://example.com/

初回のみ: playwright install chromium
出力: img/<出力名>.jpg（幅800px・ファーストビュー）
"""
import subprocess
import sys
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent.parent
IMG = BASE / 'img'


def main() -> None:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit('playwrightが必要です: pip install playwright && playwright install chromium')

    jobs = []
    for arg in sys.argv[1:]:
        name, _, url = arg.partition('=')
        if not url:
            sys.exit(f'引数の形式が不正: {arg}（<出力名>=<URL>）')
        jobs.append((name, url))
    if not jobs:
        sys.exit('引数がありません')

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={'width': 1280, 'height': 800},
                                device_scale_factor=1.25)
        for name, url in jobs:
            try:
                page.goto(url, wait_until='load', timeout=45000)
                time.sleep(3)  # 遅延描画・ヒーローアニメーション待ち
                out = IMG / f'{name}.jpg'
                page.screenshot(path=str(out), type='jpeg', quality=80)
                # 幅800pxへ縮小（macOSはsips、無ければPlaywright解像度のまま）
                subprocess.run(['sips', '--resampleWidth', '800', str(out)],
                               capture_output=True)
                print(f'  OK: {out.name} <- {url}')
            except Exception as e:
                print(f'  NG: {name} ({url}): {e}')
        browser.close()


if __name__ == '__main__':
    main()
