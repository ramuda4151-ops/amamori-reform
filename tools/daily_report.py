# -*- coding: utf-8 -*-
"""日次SEOレポートをDiscordに投稿する

データソース:
- Google Search Console API（サービスアカウント）: 記事別の表示回数・クリック・平均順位
- GASクリックロガー: 記事別のLP遷移数・電話タップ数

必要な環境変数:
- GSC_SA_KEY: サービスアカウントのJSONキー（文字列）
- DISCORD_WEBHOOK_URL: Discord WebhookのURL
- GAS_STATS_URL: GASウェブアプリのURL（未設定ならLP遷移数はスキップ)

GSCのデータは確定まで2日程度かかるため、2日前(PT基準)のデータを報告する。
"""
import datetime
import json
import os
import sys
import urllib.parse
import urllib.request

SITE = 'sc-domain:amamori-reform.com'
DOMAIN = 'https://amamori-reform.com'

PAGES = {
    '/': 'トップ',
    '/machida/': '町田',
    '/sagamihara/': '相模原',
    '/yokohama/': '横浜',
    '/kawasaki/': '川崎',
    '/fujisawa/': '藤沢',
    '/yokosuka/': '横須賀',
    '/saitama/': 'さいたま',
    '/chiba/': '千葉',
    '/funabashi/': '船橋',
    '/hachioji/': '八王子',
    '/sendai/': '仙台',
}
LPID_TO_PATH = {}  # amarefo_machida -> /machida/
for path in PAGES:
    slug = path.strip('/')
    if slug:
        LPID_TO_PATH[f'amarefo_{slug}'] = path


def gsc_token(sa_json):
    """サービスアカウントJWTでアクセストークンを取得（依存ライブラリなし）"""
    import base64
    import time

    try:
        from cryptography.hazmat.primitives import hashes, serialization
        from cryptography.hazmat.primitives.asymmetric import padding
    except ImportError:
        sys.exit('cryptography パッケージが必要です: pip install cryptography')

    sa = json.loads(sa_json)
    now = int(time.time())
    header = {'alg': 'RS256', 'typ': 'JWT'}
    claim = {
        'iss': sa['client_email'],
        'scope': 'https://www.googleapis.com/auth/webmasters.readonly',
        'aud': 'https://oauth2.googleapis.com/token',
        'iat': now,
        'exp': now + 3600,
    }

    def b64(d):
        return base64.urlsafe_b64encode(json.dumps(d).encode()).rstrip(b'=')

    signing_input = b64(header) + b'.' + b64(claim)
    key = serialization.load_pem_private_key(sa['private_key'].encode(), password=None)
    sig = key.sign(signing_input, padding.PKCS1v15(), hashes.SHA256())
    jwt = signing_input + b'.' + base64.urlsafe_b64encode(sig).rstrip(b'=')

    body = urllib.parse.urlencode({
        'grant_type': 'urn:ietf:params:oauth:grant-type:jwt-bearer',
        'assertion': jwt.decode(),
    }).encode()
    req = urllib.request.Request('https://oauth2.googleapis.com/token', data=body, method='POST')
    with urllib.request.urlopen(req) as r:
        return json.load(r)['access_token']


def gsc_query(token, date):
    url = f'https://searchconsole.googleapis.com/webmasters/v3/sites/{urllib.parse.quote(SITE, safe="")}/searchAnalytics/query'
    body = json.dumps({
        'startDate': date,
        'endDate': date,
        'dimensions': ['page'],
        'rowLimit': 100,
    }).encode()
    req = urllib.request.Request(url, data=body, method='POST', headers={
        'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as r:
        rows = json.load(r).get('rows', [])
    out = {}
    for row in rows:
        path = row['keys'][0].replace(DOMAIN, '') or '/'
        out[path] = {
            'imp': int(row.get('impressions', 0)),
            'clicks': int(row.get('clicks', 0)),
            'pos': round(row.get('position', 0), 1),
        }
    return out


def gas_counts(gas_url, date_jst):
    try:
        with urllib.request.urlopen(f'{gas_url}?date={date_jst}', timeout=30) as r:
            return json.load(r).get('counts', {})
    except Exception as e:
        print(f'GAS取得失敗: {e}')
        return {}


def post_discord(webhook, content):
    body = json.dumps({'content': content}).encode()
    req = urllib.request.Request(webhook, data=body, method='POST',
                                 headers={'Content-Type': 'application/json'})
    urllib.request.urlopen(req)


def main():
    sa_json = os.environ.get('GSC_SA_KEY')
    webhook = os.environ.get('DISCORD_WEBHOOK_URL')
    gas_url = os.environ.get('GAS_STATS_URL', '')
    if not sa_json or not webhook:
        sys.exit('GSC_SA_KEY / DISCORD_WEBHOOK_URL が未設定です')

    today = datetime.date.today()
    gsc_date = (today - datetime.timedelta(days=2)).isoformat()   # GSC確定分
    click_date = (today - datetime.timedelta(days=1)).isoformat() # クリックは昨日分

    token = gsc_token(sa_json)
    gsc = gsc_query(token, gsc_date)
    clicks = gas_counts(gas_url, click_date) if gas_url else {}
    lp_by_path = {}
    for lpid, c in clicks.items():
        path = LPID_TO_PATH.get(lpid)
        if path:
            lp_by_path[path] = c

    lines = []
    lines.append(f'**☔ 雨漏りリフォームナビ 日次レポート**')
    lines.append(f'検索データ: {gsc_date}（GSC確定分・PT基準） / LP遷移: {click_date}（JST）')
    lines.append('```')
    lines.append(f'{"記事":　<6}{"表示":>6} {"ｸﾘｯｸ":>5} {"順位":>6} {"LP遷移":>6} {"電話":>4}')
    t_imp = t_clk = t_lp = t_tel = 0
    for path, name in PAGES.items():
        g = gsc.get(path, {})
        c = lp_by_path.get(path, {})
        imp, clk, pos = g.get('imp', 0), g.get('clicks', 0), g.get('pos', '-')
        lp, tel = c.get('lp_click', 0), c.get('tel_click', 0)
        t_imp += imp; t_clk += clk; t_lp += lp; t_tel += tel
        lines.append(f'{name:　<6}{imp:>6} {clk:>5} {str(pos):>6} {lp:>6} {tel:>4}')
    lines.append('-' * 40)
    lines.append(f'{"合計":　<6}{t_imp:>6} {t_clk:>5} {"":>6} {t_lp:>6} {t_tel:>4}')
    lines.append('```')
    if not gsc:
        lines.append('※GSCデータがまだありません（新規サイトはデータ反映まで数日かかります）')

    post_discord(webhook, '\n'.join(lines))
    print('posted')


if __name__ == '__main__':
    main()
