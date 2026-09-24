/**
 * 雨漏りリフォームナビ CTAクリック計測（GASウェブアプリ）
 *
 * セットアップ:
 * 1. script.google.com → 新しいプロジェクト → このコードを貼り付け
 * 2. 初回のみ logClick をエディタから1回実行して権限承認（スプレッドシート自動作成）
 * 3. デプロイ → 新しいデプロイ → 種類: ウェブアプリ
 *    - 次のユーザーとして実行: 自分
 *    - アクセスできるユーザー: 全員
 * 4. 発行されたウェブアプリURLをClaude（site_config.jsonのgas_click_url）に渡す
 *
 * ※更新時は「デプロイを管理→新バージョン」を使うこと（URLが変わらない）
 */

var SHEET_NAME = 'clicks';

function getSheet() {
  var props = PropertiesService.getScriptProperties();
  var id = props.getProperty('SHEET_ID');
  var ss;
  if (id) {
    ss = SpreadsheetApp.openById(id);
  } else {
    ss = SpreadsheetApp.create('amamori-reform クリックログ');
    props.setProperty('SHEET_ID', ss.getId());
  }
  var sh = ss.getSheetByName(SHEET_NAME);
  if (!sh) {
    sh = ss.insertSheet(SHEET_NAME);
    sh.appendRow(['timestamp', 'date_jst', 'type', 'lp_id', 'page']);
  }
  return sh;
}

// 動作確認用（初回の権限承認にも使う）
function logClick() {
  getSheet().appendRow([new Date(), dateJst(new Date()), 'test', 'test', '/test/']);
}

function dateJst(d) {
  return Utilities.formatDate(d, 'Asia/Tokyo', 'yyyy-MM-dd');
}

// ビーコン受信（記事のCTAクリック時にsendBeaconで叩かれる）
function doPost(e) {
  try {
    var data = JSON.parse(e.postData.contents);
    var type = String(data.t || '').slice(0, 20);
    var id = String(data.id || '').slice(0, 50);
    var page = String(data.p || '').slice(0, 100);
    if (type === 'lp_click' || type === 'tel_click') {
      var now = new Date();
      getSheet().appendRow([now, dateJst(now), type, id, page]);
    }
  } catch (err) {}
  return ContentService.createTextOutput('ok');
}

// 集計取得（?date=YYYY-MM-DD 指定日のlp_id別クリック数を返す）
function doGet(e) {
  var date = (e.parameter && e.parameter.date) || dateJst(new Date());
  var sh = getSheet();
  var values = sh.getDataRange().getValues();
  var out = {}; // {lp_id: {lp_click: n, tel_click: n}}
  for (var i = 1; i < values.length; i++) {
    var row = values[i];
    if (row[1] !== date) continue;
    var id = row[3] || 'unknown';
    if (!out[id]) out[id] = { lp_click: 0, tel_click: 0 };
    if (row[2] === 'lp_click') out[id].lp_click++;
    if (row[2] === 'tel_click') out[id].tel_click++;
  }
  return ContentService.createTextOutput(JSON.stringify({ date: date, counts: out }))
    .setMimeType(ContentService.MimeType.JSON);
}
