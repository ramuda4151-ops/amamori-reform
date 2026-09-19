# -*- coding: utf-8 -*-
"""雨漏りリフォームナビ ビルドスクリプト

data/<slug>.json × template/article.html から全記事を生成し、
トップページ(index.html)・sitemap.xml も自動生成する。

使い方:
    python3 build.py          # 全ページ生成 + lint
    python3 build.py machida  # 指定slugのみ生成 + lint
"""
import glob
import json
import os
import re
import sys

BASE = os.path.dirname(os.path.abspath(__file__))
DOMAIN = 'https://amamori-reform.com'
WDAYS = ['月', '火', '水', '木', '金', '土', '日']


def ja_date(iso):
    y, m, d = iso.split('-')
    return f'{int(y)}年{int(m)}月{int(d)}日'


def load_data():
    items = []
    for p in sorted(glob.glob(f'{BASE}/data/*.json')):
        if p.endswith('notion_db.json'):
            continue
        with open(p, encoding='utf-8') as f:
            items.append(json.load(f))
    # order（小さいほど上）→ 公開日で整列
    items.sort(key=lambda d: (d.get('order', 999), d['date_pub'], d['slug']))
    return items


def render_article(d, tpl):
    out = tpl
    reps = {
        '{{TABLE_ROWS}}': d['rows_html'],
        '{{COMPANY_CARDS}}': d['cards_html'],
        '{{INTRO_LOCAL}}': d['intro_local'],
        '{{CONSUMER_CENTER}}': d['consumer_center'],
        '{{PREF}}': d['pref'],
        '{{CITY}}': d['city'],
        '{{SLUG}}': d['slug'],
        '{{LP}}': d['lp'],
        '{{LPID}}': d['lpid'],
        '{{AREA_WIDE}}': d['area_wide'],
        '{{DATE_PUB}}': d['date_pub'],
        '{{DATE_MOD}}': d['date_mod'],
        '{{DATE_MOD_JA}}': '最終更新：' + ja_date(d['date_mod']),
    }
    # 表示用の「最終更新：」はテンプレ側に含まれるため、素の日付だけ差し込む
    reps['{{DATE_MOD_JA}}'] = ja_date(d['date_mod'])
    for k, v in reps.items():
        out = out.replace(k, v)
    return out


def render_top(items, tpl):
    cards = []
    for d in items:
        cards.append(f'''    <a class="post-card" href="/{d['slug']}/">
      <div class="post-thumb"><div class="pref">{d['pref']}</div><div class="area">{d['city']}</div></div>
      <div class="post-body">
        <div class="pt">【{d['city']}】雨漏り修理業者おすすめ5選を徹底比較！費用相場と失敗しない選び方</div>
        <div class="pd">{ja_date(d['date_mod'])}</div>
        <div class="tag">地域別ガイド</div>
      </div>
    </a>''')
    return tpl.replace('{{POST_CARDS}}', '\n'.join(cards))


def render_sitemap(items):
    top_mod = max(d['date_mod'] for d in items)
    s = '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
    s += f'  <url>\n    <loc>{DOMAIN}/</loc>\n    <lastmod>{top_mod}</lastmod>\n  </url>\n'
    for d in items:
        s += f'  <url>\n    <loc>{DOMAIN}/{d["slug"]}/</loc>\n    <lastmod>{d["date_mod"]}</lastmod>\n  </url>\n'
    s += '</urlset>\n'
    return s


def lint(path, html):
    errs = []
    if '{{' in html:
        errs.append('未置換プレースホルダあり: ' + ','.join(set(re.findall(r'\{\{\w+\}\}', html))))
    if '雨漏りレスキュー' in html:
        errs.append('旧サイト名が残存')
    for img in re.findall(r'(?:\.\./)?img/([\w.-]+\.(?:webp|jpg|png|svg))', html):
        if not os.path.exists(f'{BASE}/img/{img}'):
            errs.append(f'画像なし: img/{img}')
    for e in errs:
        print(f'  LINT NG [{path}] {e}')
    return not errs


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    tpl = open(f'{BASE}/template/article.html', encoding='utf-8').read()
    top_tpl = open(f'{BASE}/template/top.html', encoding='utf-8').read()
    items = load_data()
    ok = True

    for d in items:
        if only and d['slug'] != only:
            continue
        html = render_article(d, tpl)
        os.makedirs(f'{BASE}/{d["slug"]}', exist_ok=True)
        with open(f'{BASE}/{d["slug"]}/index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        ok &= lint(d['slug'], html)
        print(f'  built: {d["slug"]}/index.html')

    top = render_top(items, top_tpl)
    with open(f'{BASE}/index.html', 'w', encoding='utf-8') as f:
        f.write(top)
    ok &= lint('index', top)
    with open(f'{BASE}/sitemap.xml', 'w') as f:
        f.write(render_sitemap(items))
    print('  built: index.html, sitemap.xml')

    if not ok:
        sys.exit(1)
    print('build OK')


if __name__ == '__main__':
    main()
