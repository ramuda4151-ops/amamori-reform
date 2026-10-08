# 記事制作パイプライン（自動実行エージェント向け手順書）

雨漏りリフォームナビ（amamori-reform.com）の地域記事を制作・公開する完全な手順。
毎日の定期実行では `data/queue.json` の先頭から **3市** を処理する。

## 前提

- 生成HTMLは手編集禁止。すべて `template/` + `data/<slug>.json` + `python3 build.py`
- 市のメタ情報（slug/市名/県/地方/lp/batch）は `data/queue.json` から取得し、処理済みはキューから削除してコミットに含める
- 既存記事のデータ構造は `data/machida.json` 等を参照（同じキー構成で作る）

## 1市あたりの手順

### 1. リサーチ（WebSearch / WebFetch）

「雨漏り修理 〇〇市 業者 おすすめ」等で検索し、地元業者を**3社**選定する。

選定基準（すべて必須）:
- 業者自身の公式サイトがある（比較サイト・ポータル・全国紹介サービスは除外。雨漏り修理110番は記事側に既出のため特に除外）
- **公式サイトに現地調査または見積もり無料の明記がある**（最重要。明記が確認できない業者は掲載不可）
- 3社のタイプを分散（例: 雨漏り/屋根専門店・屋根工事店・塗装/防水店）
- 事実は公式サイトから収集。推測で埋めない。不明項目は書かない

あわせて収集するもの:
- 市の地域特性1〜2文（築古戸建て・塩害・雪害・台風被害など事実ベース。導入文に使用）
- 市の消費生活センターの正式名称
- （可能なら）市の住宅修繕・リフォーム助成金制度の有無と概要 → extra_html セクションに使用

### 2. スクリーンショット

```
python3 tools/screenshot.py site_<業者名ローマ字>=<公式サイトURL> ×3社分
```
- 要: playwright + chromium。クラウド実行環境では `/opt/pw-browsers` のプリインストール版に合わせ
  `pip install playwright==1.56.0`（`playwright install` は不要）。ローカルは `pip install playwright && playwright install chromium`
- ChromiumがTLS再終端プロキシ等で外部サイトに到達できない場合、スクリプトが自動で
  mShots API（サーバーサイドスクショ）にフォールバックする。TLS検証の無効化は試みないこと
- 撮影後、`img/site_*.jpg` が10KB以上で生成されているか確認する

### 3. data/<slug>.json 作成

既存ファイル（data/saitama.json等）と同じ構造で作成:
- `intro_local`: 市の地域特性（「〇〇市は」で始め「〜エリア。」で終える体言止め推奨）
- `rows_html`: 比較表2〜4位の行（順位セル付き。タイプ列に「雨漏り専門」系は使わない。
  雨漏り寄りの業者は「リフォーム店<br>（雨漏り修理も対応）」等にする。1位の雨漏り修理専門はアメトメ専用）
- `cards_html`: 2〜4位の業者カード（h3タイトル・site-shotフィギュア・紹介文・check3点・ext-link必須。
  紹介文は公式サイトの事実のみ、1文に1つ `<span class="mk">強調</span>`）
- `lpid`: `amarefo_<slug>` / `lp`: 関東=lp1・東北=lp3 / `area_wide`: 関東全域 or 東北全域
- `nearby`: 費用相場の地域表現（例: 埼玉県内・宮城県内・東京近郊）
- `date_pub` = `date_mod` = 当日の**JST日付**（実行環境がUTCの場合ズレるため `TZ=Asia/Tokyo date +%F` で取得）、`order` = 既存最大値+1
- `extra_html`（任意）: 市の助成金情報等の固有セクション（h2 + p数個。事実が取れた場合のみ）

### 4. ビルドと公開

```
python3 build.py        # 全記事再生成 + lint（エラーで止まったら修正）
git add -A && git commit -m "feat: 〇〇市の記事を追加" && git push
```

- push後1〜2分でGitHub Pagesに反映される。`curl -s https://amamori-reform.com/<slug>/ | grep amarefo_<slug>` で確認
- sitemap.xmlはbuildが自動更新するため、インデックス登録リクエストは不要

### 5. 品質チェックリスト（公開前に必ず）

- [ ] 3社とも調査/見積もり無料の明記を確認した
- [ ] 比較表のタイプ列で「雨漏り専門」を名乗るのはアメトメ1位のみ
- [ ] 業者カードの事実（実績数・保証・受付時間）は公式サイト由来
- [ ] `{{` が残っていない（lintが検知）
- [ ] 市名の取り違えがない（他市の業者カードをコピーした痕跡等）

## 情報記事（お役立ちコラム）の制作手順

毎日の定期実行では、地域記事3市に加えて `data/info_queue.json` の先頭から**情報記事を1本**制作する。

1. info_queue.json 先頭のテーマ（slug/title_short/query/point）を確認し、狙うクエリで上位表示中の記事の見出し構成をリサーチする
2. `data/oukyushochi.json` と同じ構造で `data/<slug>.json` を作成（`type: "info"` 必須）:
   - `title`: 32文字前後、狙うクエリの語を含める / `title_short`: 関連リンク用の短縮名
   - `body_html`: 既存CSSクラスのみ使用（toc / h2・h3 / check / warn-box / mk / faq-q・faq-a / figure / cta-box）。
     3,000〜4,000字、リード→目次→本文→中間CTA→FAQの構成。oukyushochi.json の書きぶり・一人称（管理人）を踏襲
   - `head_extra`: FAQPage JSON-LD（本文のFAQと同内容）
   - `hero`: img/ 内の既存 photo_*.webp から選ぶ（新規画像は不要）
   - `lpid`: `amarefo_<slug>` / `lp`: 原則lp1（すが漏れ等の東北テーマはlp3）/ `order`: 情報記事は101から連番
3. 事実の扱い: 医学・法律・保険の断定をしない（「〜ことがあります」）。「保険適用の判断は保険会社」を厳守。
   統計や制度に言及する場合は公的機関（消費者庁・国民生活センター等）の公開情報のみを根拠にする
4. 処理済みテーマは info_queue.json から削除し、地域記事と同じコミットに含める
5. build.py のlintが通ること。info_queue.json が空なら情報記事はスキップ

## 制約・注意

- 1回の実行で処理するのは地域3市＋コラム1本まで（品質維持とセッション上限の観点）。
  1日の実行回数に上限はない。量より質: 無料明記の確認が取れない業者を無理に載せるくらいなら本数を減らす
- Clarityタグ・クリック計測は site_config.json 設定済みならbuildが自動注入する（触らない）
- 位置図（img/map_<slug>.svg）が無い市は `tools/` の gen_maps 相当が未対応。地図が無い場合、
  テンプレートの地図figureが404になるため、**必ず map_<slug>.svg を生成するか確認する**
  （座標は市庁舎付近。既存SVGの構造を踏襲）
