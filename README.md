# 玉器・古陶磁・古美術 調査データベース

翡翠・白玉・和田白玉・古玉・古陶磁・陶芸アンティーク・芸術品の  
ネット調査結果・論文・博物館資料・オークション事例・真贋判断・偽物特徴を  
蓄積し、後から検索・比較・評価できるSQLiteデータベース。

---

## 目的

| 機能 | 説明 |
|------|------|
| 購入判断 | リスクスコア0〜100点で購入可否を評価 |
| 真贋リスク評価 | 50以上の判定フラグによる詳細な偽物リスク分析 |
| 相場比較 | オークション落札事例との価格比較 |
| 歴史背景確認 | 論文・博物館資料との紐づけ |
| 偽物特徴蓄積 | カテゴリ別偽物特徴ライブラリ |

---

## ディレクトリ構成

```
jade-ceramics-research/
├── data/
│   ├── antiques.db          # SQLiteデータベース
│   └── csv/                 # CSVインポート用ファイル置き場
├── images/
│   ├── jade/                # 翡翠
│   ├── white_jade/          # 白玉
│   ├── hetian_jade/         # 和田白玉
│   ├── ceramics/            # 陶磁器
│   ├── fake_examples/       # 偽物例
│   └── auction/             # オークション画像
├── reports/                 # 出力されたMarkdownレポート
├── scripts/
│   ├── init_db.py           # DB初期化
│   ├── import_csv.py        # CSVインポート
│   ├── add_item.py          # 1件登録（JSON入力）
│   ├── search_items.py      # 検索
│   └── export_report.py     # レポート出力
└── src/
    ├── db.py                # DB接続管理
    ├── models.py            # SQLiteスキーマ定義
    ├── risk_score.py        # リスクスコア計算エンジン
    └── report_writer.py     # Markdownレポート生成
```

---

## セットアップ

```bash
pip install -r requirements.txt
```

---

## 使い方

### 1. DB初期化

```bash
python3 scripts/init_db.py
```

`data/antiques.db` が作成されます。

---

### 2. CSVからデータ投入

```bash
# data/csv/ 以下のすべてのCSVを一括インポート
python3 scripts/import_csv.py

# ファイルを指定してインポート
python3 scripts/import_csv.py data/csv/items_sample.csv
```

**CSVファイル命名規則：**

| ファイル名プレフィックス | 対象テーブル |
|------------------------|------------|
| `items_*.csv`          | 作品データ＋真贋評価 |
| `references_*.csv`     | 論文・資料 |
| `fake_features_*.csv`  | 偽物特徴 |
| `auctions_*.csv`       | オークション比較 |

テンプレートは `templates/` フォルダを参照してください。

---

### 3. 検索

```bash
# キーワード検索
python3 scripts/search_items.py -k 翡翠

# 分類・材質・年代で絞り込み
python3 scripts/search_items.py -c 古玉 -m 和田白玉

# 価格帯・リスクスコアで絞り込み
python3 scripts/search_items.py --price-max 500000 --risk-max 40

# 鑑別書あり・返品可のみ
python3 scripts/search_items.py --has-cert --returnable

# すべてのオプション
python3 scripts/search_items.py --help
```

**検索オプション一覧：**

| オプション | 説明 |
|-----------|------|
| `-k KEYWORD` | キーワード（名称・説明・材質・販売者） |
| `-c CATEGORY` | 分類（部分一致） |
| `-m MATERIAL` | 材質（部分一致） |
| `-p PERIOD` | 推定年代（部分一致） |
| `--price-min N` | 価格下限 |
| `--price-max N` | 価格上限 |
| `--risk-min N` | リスクスコア下限 |
| `--risk-max N` | リスクスコア上限 |
| `-s SELLER` | 販売者（部分一致） |
| `--has-cert` | 鑑別書ありのみ |
| `--returnable` | 返品可のみ |

---

### 4. Markdownレポート出力

```bash
# 作品ID=2 のレポートを出力
python3 scripts/export_report.py 2

# すべての作品のレポートを出力
python3 scripts/export_report.py --all
```

レポートは `reports/` フォルダに保存されます。

**レポート内容：**
1. 結論（リスクスコア・購入判断）
2. 基本情報
3. 画像一覧
4. 真贋リスク評価（加点・減点項目の詳細）
5. 偽物特徴との一致
6. 類似オークション比較
7. 関連論文・資料
8. 購入判断
9. 追加確認事項

---

### 5. 1件ずつJSONで登録

```bash
python3 scripts/add_item.py item_data.json
```

JSONファイルの形式：

```json
{
  "item": {
    "name": "清代 和田白玉 龍佩",
    "category": "白玉",
    "material": "和田白玉（ネフライト）",
    "estimated_period": "清代",
    "price": 1500000,
    "currency": "JPY",
    "seller": "例：銀座○○堂",
    "source_url": "https://example.com/item/xxx",
    "has_certificate": 1,
    "returnable": 0
  },
  "assessment": {
    "no_certificate": 0,
    "few_photos": 1,
    "no_transmitted_light": 1,
    "authenticity_probability": "中",
    "reasoning": "鑑別書あり。ただし透過光写真不足。"
  },
  "images": [
    {
      "filename": "front.jpg",
      "file_path": "images/white_jade/front.jpg",
      "image_type": "正面",
      "source_url": "https://example.com/img/front.jpg"
    }
  ]
}
```

---

## リスクスコア仕様

| スコア | リスクレベル | 購入判断 |
|--------|------------|---------|
| 0〜20  | 🟢 低リスク | 購入候補 |
| 21〜40 | 🟡 注意 | 追加確認後に検討 |
| 41〜60 | 🟠 要警戒 | 原則慎重 |
| 61〜80 | 🔴 高リスク | 基本購入しない |
| 81〜100| ⛔ 購入非推奨 | 購入非推奨 |

**強制高リスク判定：** 以下に該当する場合、スコアに関係なく最低61点。
- 商品写真の流用が濃厚
- 鑑別書と商品が対応していない
- 人工処理疑い（樹脂含浸・染色・酸処理）
- 古玉表記なのに来歴なし
- 出土品表記なのに合法性説明なし

---

## 対象カテゴリ

`翡翠` / `白玉` / `和田白玉` / `古玉` / `古陶磁` / `陶芸アンティーク` / `芸術品`

---

## 注意事項

本データベースは**購入判断支援用のリスク評価ツール**です。  
断定的な真贋鑑定ではありません。  
最終的な判断は専門家の鑑定を参考にしてください。
