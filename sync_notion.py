# -*- coding: utf-8 -*-
"""記事メタデータをNotionの「SEO記事管理」DBへupsertする。

実行: op run --env-file=.env.op -- python3 sync_notion.py
初回はDBを自動作成し、IDを data/notion_db.json に保存する。
"""
import glob
import json
import os
import sys
import urllib.request

TOKEN = os.environ.get('NOTION_TOKEN')
if not TOKEN:
    sys.exit('NOTION_TOKEN がありません。op run --env-file=.env.op -- python3 sync_notion.py で実行してください')

BASE = os.path.dirname(os.path.abspath(__file__))
PARENT_PAGE_ID = '3e039063fa788070b14cc244e30c5418'  # 「アメトメSEO」ページ
DB_META = f'{BASE}/data/notion_db.json'
DOMAIN = 'https://amamori-reform.com'
API = 'https://api.notion.com/v1'
HEADERS = {
    'Authorization': f'Bearer {TOKEN}',
    'Notion-Version': '2022-06-28',
    'Content-Type': 'application/json',
}


def req(method, path, body=None):
    r = urllib.request.Request(API + path, method=method, headers=HEADERS,
                               data=json.dumps(body).encode() if body else None)
    try:
        with urllib.request.urlopen(r) as res:
            return json.load(res)
    except urllib.error.HTTPError as e:
        sys.exit(f'Notion API error {e.code} {path}: {e.read().decode()[:300]}')


def get_db_id():
    if os.path.exists(DB_META):
        return json.load(open(DB_META))['database_id']
    db = req('POST', '/databases', {
        'parent': {'type': 'page_id', 'page_id': PARENT_PAGE_ID},
        'title': [{'type': 'text', 'text': {'content': 'SEO記事管理'}}],
        'properties': {
            '記事名': {'title': {}},
            'URL': {'url': {}},
            'ステータス': {'select': {'options': [
                {'name': '候補', 'color': 'gray'},
                {'name': '調査中', 'color': 'yellow'},
                {'name': '公開済', 'color': 'green'},
                {'name': 'リライト', 'color': 'orange'},
            ]}},
            '地方': {'select': {'options': [
                {'name': '関東', 'color': 'blue'},
                {'name': '東北', 'color': 'purple'},
                {'name': '九州', 'color': 'pink'},
            ]}},
            '都道府県': {'select': {}},
            '市': {'rich_text': {}},
            'lp_id': {'rich_text': {}},
            '送客先LP': {'select': {'options': [
                {'name': 'lp1(関東)', 'color': 'blue'},
                {'name': 'lp3(東北)', 'color': 'purple'},
                {'name': 'lp4(福岡)', 'color': 'pink'},
            ]}},
            '公開日': {'date': {}},
            '最終更新': {'date': {}},
            '掲載業者': {'rich_text': {}},
            'メモ': {'rich_text': {}},
        },
    })
    json.dump({'database_id': db['id']}, open(DB_META, 'w'))
    print(f"DB作成: SEO記事管理 ({db['id']})")
    return db['id']


def rt(s):
    return [{'type': 'text', 'text': {'content': s[:1900]}}]


def upsert(db_id, d):
    lp_label = {'lp1': 'lp1(関東)', 'lp3': 'lp3(東北)', 'lp4': 'lp4(福岡)'}[d['lp']]
    props = {
        '記事名': {'title': rt(f"【{d['city']}】雨漏り修理業者おすすめ5選")},
        'URL': {'url': f"{DOMAIN}/{d['slug']}/"},
        'ステータス': {'select': {'name': '公開済'}},
        '地方': {'select': {'name': d['region']}},
        '都道府県': {'select': {'name': d['pref']}},
        '市': {'rich_text': rt(d['city'])},
        'lp_id': {'rich_text': rt(d['lpid'])},
        '送客先LP': {'select': {'name': lp_label}},
        '公開日': {'date': {'start': d['date_pub']}},
        '最終更新': {'date': {'start': d['date_mod']}},
        '掲載業者': {'rich_text': rt(' / '.join(d['companies']))},
    }
    hit = req('POST', f'/databases/{db_id}/query', {
        'filter': {'property': 'lp_id', 'rich_text': {'equals': d['lpid']}},
    })['results']
    if hit:
        req('PATCH', f"/pages/{hit[0]['id']}", {'properties': props})
        print(f"  updated: {d['city']}")
    else:
        req('POST', '/pages', {'parent': {'database_id': db_id}, 'properties': props})
        print(f"  created: {d['city']}")


def main():
    db_id = get_db_id()
    for p in sorted(glob.glob(f'{BASE}/data/*.json')):
        if p.endswith('notion_db.json'):
            continue
        with open(p, encoding='utf-8') as f:
            d = json.load(f)
        upsert(db_id, d)
    print('sync OK')


if __name__ == '__main__':
    main()
