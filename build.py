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
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        if not isinstance(d, dict) or 'slug' not in d:
            continue  # queue.json / notion_db.json 等はスキップ
        items.append(d)
    # order（小さいほど上）→ 公開日で整列
    items.sort(key=lambda d: (d.get('order', 999), d['date_pub'], d['slug']))
    return items


def link_title(d):
    if d.get('type') == 'info':
        return d['title_short']
    return f'【{d["city"]}】雨漏り修理業者おすすめランキング5選'


def related_html(d, items):
    """関連記事リンク（最大4件）のセクションHTMLを返す

    地域記事: 同県→同地方の近隣記事。情報記事: 他の情報記事→地域記事の順
    """
    others = [x for x in items if x['slug'] != d['slug']]
    if d.get('type') == 'info':
        picks = [x for x in others if x.get('type') == 'info'][:4]
        heading = 'あわせて読みたい'
    else:
        picks = [x for x in others if x.get('pref') == d.get('pref') and x.get('type') != 'info']
        picks += [x for x in others
                  if x.get('region') == d.get('region') and x.get('type') != 'info'
                  and x not in picks]
        # 近隣枠の末尾に情報記事を1本混ぜて回遊させる
        infos = [x for x in others if x.get('type') == 'info']
        picks = picks[:3] + infos[:1] if infos else picks[:4]
        heading = '近隣エリアの雨漏り修理業者情報'
    if not picks:
        return ''
    lis = '\n'.join(
        f'        <li><a href="/{x["slug"]}/">{link_title(x)}</a></li>' for x in picks)
    return f'''    <section class="related">
      <h2>{heading}</h2>
      <ul>
{lis}
      </ul>
    </section>
'''


def render_info(d, tpl, items):
    out = tpl
    reps = {
        '{{RELATED}}': related_html(d, items),
        '{{TITLE}}': d['title'],
        '{{TITLE_SHORT}}': d['title_short'],
        '{{DESC}}': d['desc'],
        '{{HERO}}': d['hero'],
        '{{HERO_CAPTION}}': d.get('hero_caption', ''),
        '{{BODY}}': d['body_html'],
        '{{HEAD_EXTRA}}': d.get('head_extra', ''),
        '{{SLUG}}': d['slug'],
        '{{LP}}': d.get('lp', 'lp1'),
        '{{LPID}}': d['lpid'],
        '{{DATE_PUB}}': d['date_pub'],
        '{{DATE_MOD}}': d['date_mod'],
        '{{DATE_MOD_JA}}': ja_date(d['date_mod']),
    }
    for k, v in reps.items():
        out = out.replace(k, v)
    return out


def render_article(d, tpl, items):
    out = tpl
    reps = {
        '{{RELATED}}': related_html(d, items),
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
        '{{NEARBY}}': d.get('nearby', '東京近郊'),
        '{{EXTRA}}': d.get('extra_html', ''),
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
        if d.get('type') == 'info':
            thumb = '<div class="pref">コラム</div><div class="area">お役立ち</div>'
            title = d['title']
            tag = 'お役立ちコラム'
        else:
            thumb = f"<div class=\"pref\">{d['pref']}</div><div class=\"area\">{d['city']}</div>"
            title = f"【{d['city']}】雨漏り修理業者おすすめランキング5選！費用相場と失敗しない選び方"
            tag = '地域別ガイド'
        cards.append(f'''    <a class="post-card" href="/{d['slug']}/">
      <div class="post-thumb">{thumb}</div>
      <div class="post-body">
        <div class="pt">{title}</div>
        <div class="pd">{ja_date(d['date_mod'])}</div>
        <div class="tag">{tag}</div>
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


CLARITY_SNIPPET = '''<script type="text/javascript">
    (function(c,l,a,r,i,t,y){
        c[a]=c[a]||function(){(c[a].q=c[a].q||[]).push(arguments)};
        t=l.createElement(r);t.async=1;t.src="https://www.clarity.ms/tag/"+i;
        y=l.getElementsByTagName(r)[0];y.parentNode.insertBefore(t,y);
    })(window, document, "clarity", "script", "%s");
  </script>
'''


BEACON_SNIPPET = '''<script>
    (function(){
      var EP="%s";
      function send(t){
        var a=document.querySelector('a[href*="asp.amamori-tometai.com"]');
        var id=""; try{ id=new URL(a.href).searchParams.get("id")||""; }catch(_){}
        try{ navigator.sendBeacon(EP, JSON.stringify({t:t,id:id,p:location.pathname})); }catch(_){}
      }
      document.addEventListener("click", function(e){
        var a=e.target && e.target.closest ? e.target.closest("a") : null;
        if(!a) return;
        if(a.href && a.href.indexOf("asp.amamori-tometai.com")>-1) send("lp_click");
        else if(a.href && a.href.indexOf("tel:")===0) send("tel_click");
      }, true);
    })();
  </script>
'''


def inject_clarity(html):
    cfg_path = f'{BASE}/site_config.json'
    if not os.path.exists(cfg_path):
        return html
    cfg = json.load(open(cfg_path))
    cid = cfg.get('clarity_id', '')
    if cid:
        html = html.replace('</head>', CLARITY_SNIPPET % cid + '</head>', 1)
    gas = cfg.get('gas_click_url', '')
    if gas:
        html = html.replace('</head>', BEACON_SNIPPET % gas + '</head>', 1)
    return html


def main():
    only = sys.argv[1] if len(sys.argv) > 1 else None
    tpl = open(f'{BASE}/template/article.html', encoding='utf-8').read()
    info_tpl = open(f'{BASE}/template/info.html', encoding='utf-8').read()
    top_tpl = open(f'{BASE}/template/top.html', encoding='utf-8').read()
    items = load_data()
    ok = True

    for d in items:
        if only and d['slug'] != only:
            continue
        if d.get('type') == 'info':
            html = inject_clarity(render_info(d, info_tpl, items))
        else:
            html = inject_clarity(render_article(d, tpl, items))
        os.makedirs(f'{BASE}/{d["slug"]}', exist_ok=True)
        with open(f'{BASE}/{d["slug"]}/index.html', 'w', encoding='utf-8') as f:
            f.write(html)
        ok &= lint(d['slug'], html)
        print(f'  built: {d["slug"]}/index.html')

    top = inject_clarity(render_top(items, top_tpl))
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
