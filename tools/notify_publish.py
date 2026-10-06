# -*- coding: utf-8 -*-
"""新規公開した記事をLINEグループに通知する（push時のGitHub Actionsから実行）

push範囲（BEFORE_SHA..AFTER_SHA）で追加された data/<slug>.json を検出し、
記事URL一覧をLINEにpushする。新規記事がなければ何も送らない。

必要な環境変数:
- LINE_CHANNEL_ACCESS_TOKEN / LINE_GROUP_ID
- BEFORE_SHA / AFTER_SHA（workflowが渡す。BEFORE_SHAが全ゼロなら直前コミット比較）
"""
import json
import os
import subprocess
import sys
import urllib.request

DOMAIN = 'https://amamori-reform.com'
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def added_article_files(before, after):
    if not before or set(before) == {'0'}:
        before = f'{after}^'
    out = subprocess.run(
        ['git', 'diff', '--name-status', before, after, '--', 'data/'],
        capture_output=True, text=True, cwd=BASE, check=True).stdout
    files = []
    for line in out.splitlines():
        parts = line.split('\t')
        if len(parts) == 2 and parts[0] == 'A' and parts[1].endswith('.json'):
            files.append(parts[1])
    return files


def post_line(token, group_id, text):
    body = json.dumps({
        'to': group_id,
        'messages': [{'type': 'text', 'text': text}],
    }).encode()
    req = urllib.request.Request(
        'https://api.line.me/v2/bot/message/push', data=body, method='POST',
        headers={'Content-Type': 'application/json',
                 'Authorization': f'Bearer {token}'})
    with urllib.request.urlopen(req) as r:
        r.read()


def main():
    token = os.environ.get('LINE_CHANNEL_ACCESS_TOKEN')
    group = os.environ.get('LINE_GROUP_ID')
    if not token or not group:
        sys.exit('LINE_CHANNEL_ACCESS_TOKEN / LINE_GROUP_ID が未設定です')

    files = added_article_files(os.environ.get('BEFORE_SHA', ''),
                                os.environ.get('AFTER_SHA', 'HEAD'))
    arts = []
    for f in files:
        path = os.path.join(BASE, f)
        if not os.path.exists(path):
            continue
        d = json.load(open(path, encoding='utf-8'))
        if isinstance(d, dict) and 'slug' in d:
            arts.append((d.get('city', d['slug']), f"{DOMAIN}/{d['slug']}/"))

    if not arts:
        print('新規記事なし（通知スキップ）')
        return

    lines = [f'🆕 記事を公開しました（{len(arts)}件）', '']
    for city, url in arts:
        lines.append(f'・{city}')
        lines.append(f'  {url}')
    post_line(token, group, '\n'.join(lines))
    print(f'posted: {len(arts)}件')


if __name__ == '__main__':
    main()
