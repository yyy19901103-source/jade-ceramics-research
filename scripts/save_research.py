#!/usr/bin/env python3
"""
ネット調査結果をDBに保存するCLIスクリプト。

使い方：
  # 資料・論文を追加してアイテムに紐付け
  python3 scripts/save_research.py ref --item 7 \
    --title "清代花形杯の研究" --author "故宮" --year 2020 \
    --type 博物館資料 --url "https://..." \
    --summary "..." --points "..." --reliability 5

  # オークション事例を追加してアイテムに紐付け
  python3 scripts/save_research.py auction --item 7 \
    --house "クリスティーズ香港" --name "清代白玉花形杯" \
    --period "清代18世紀" --material "和田白玉" \
    --hammer 3840000 --currency HKD --date 2022-11-28 \
    --memo "俏色技法の参考事例"

  # 偽物特徴を追加してアイテムに紐付け
  python3 scripts/save_research.py fake --item 7 \
    --name "特徴名" --category 白玉 --danger 4 \
    --desc "説明" --method "観察方法" --basis "判定根拠" \
    --confidence 中 --notes "一致箇所"

  # アイテムの説明・評価を更新
  python3 scripts/save_research.py update --item 7 \
    --field price --value 1500000
"""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from src.db import get_connection


def cmd_ref(args):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO references_
        (title, author, year, ref_type, url, pdf_path, summary, key_points,
         related_fake_features, related_materials, reliability)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
    """, (args.title, args.author, args.year, args.type, args.url or "",
          "", args.summary or "", args.points or "",
          args.fake_features or "", args.materials or "",
          args.reliability))
    ref_id = cur.lastrowid
    conn.commit()
    print(f"reference追加: ID={ref_id} '{args.title}'")

    if args.item:
        conn.execute("INSERT OR IGNORE INTO item_references (item_id, reference_id) VALUES (?,?)",
                     (args.item, ref_id))
        conn.commit()
        print(f"  → item {args.item} に紐付け")
    conn.close()


def cmd_auction(args):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO auctions
        (auction_house, lot_number, item_name, period, material, size_description,
         estimate_low, estimate_high, hammer_price, currency, sale_date,
         provenance, condition_description, source_url, comparison_memo)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (args.house, args.lot or "", args.name, args.period or "",
          args.material or "", args.size or "",
          args.est_low, args.est_high, args.hammer,
          args.currency or "HKD", args.date or "",
          args.provenance or "", args.condition or "",
          args.url or "", args.memo or ""))
    auc_id = cur.lastrowid
    conn.commit()
    print(f"auction追加: ID={auc_id} '{args.name}' 落札={args.hammer}{args.currency}")

    if args.item:
        conn.execute("INSERT OR IGNORE INTO item_auctions (item_id, auction_id, comparison_notes) VALUES (?,?,?)",
                     (args.item, auc_id, args.memo or ""))
        conn.commit()
        print(f"  → item {args.item} に紐付け")
    conn.close()


def cmd_fake(args):
    conn = get_connection()
    cur = conn.execute("""
        INSERT INTO fake_features
        (feature_name, target_category, description, observation_method,
         judgment_basis, reference_url, danger_level, memo)
        VALUES (?,?,?,?,?,?,?,?)
    """, (args.name, args.category or "全般", args.desc or "",
          args.method or "", args.basis or "",
          args.url or "", args.danger or 3, args.notes or ""))
    ff_id = cur.lastrowid
    conn.commit()
    print(f"fake_feature追加: ID={ff_id} '{args.name}'")

    if args.item:
        conn.execute("""INSERT OR IGNORE INTO item_fake_features
                        (item_id, fake_feature_id, match_confidence, notes) VALUES (?,?,?,?)""",
                     (args.item, ff_id, args.confidence or "中", args.notes or ""))
        conn.commit()
        print(f"  → item {args.item} に紐付け")
    conn.close()


def cmd_update(args):
    conn = get_connection()
    allowed = {"name","category","material","estimated_period","estimated_origin",
               "size_description","weight_g","price","currency","seller",
               "source_url","description","condition","accessories",
               "has_certificate","certificate_issuer","returnable"}
    if args.field not in allowed:
        print(f"ERROR: field '{args.field}' は更新不可。許可フィールド: {sorted(allowed)}")
        sys.exit(1)
    conn.execute(f"UPDATE items SET {args.field}=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
                 (args.value, args.item))
    conn.commit()
    print(f"item {args.item} の {args.field} を更新しました")
    conn.close()


def main():
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd")

    # ref
    r = sub.add_parser("ref", help="資料・論文を追加")
    r.add_argument("--item", type=int)
    r.add_argument("--title", required=True)
    r.add_argument("--author", default="")
    r.add_argument("--year", type=int)
    r.add_argument("--type", default="市場記事",
                   choices=["論文","博物館資料","オークション資料","鑑定機関資料","市場記事"])
    r.add_argument("--url")
    r.add_argument("--summary")
    r.add_argument("--points")
    r.add_argument("--fake-features")
    r.add_argument("--materials")
    r.add_argument("--reliability", type=int, default=3, choices=[1,2,3,4,5])

    # auction
    a = sub.add_parser("auction", help="オークション事例を追加")
    a.add_argument("--item", type=int)
    a.add_argument("--house", required=True)
    a.add_argument("--lot")
    a.add_argument("--name", required=True)
    a.add_argument("--period")
    a.add_argument("--material")
    a.add_argument("--size")
    a.add_argument("--est-low", type=float, default=None)
    a.add_argument("--est-high", type=float, default=None)
    a.add_argument("--hammer", type=float, required=True)
    a.add_argument("--currency", default="HKD")
    a.add_argument("--date")
    a.add_argument("--provenance")
    a.add_argument("--condition")
    a.add_argument("--url")
    a.add_argument("--memo")

    # fake
    f = sub.add_parser("fake", help="偽物特徴を追加")
    f.add_argument("--item", type=int)
    f.add_argument("--name", required=True)
    f.add_argument("--category")
    f.add_argument("--danger", type=int, default=3, choices=[1,2,3,4,5])
    f.add_argument("--desc")
    f.add_argument("--method")
    f.add_argument("--basis")
    f.add_argument("--url")
    f.add_argument("--confidence", default="中", choices=["高","中","低"])
    f.add_argument("--notes")

    # update
    u = sub.add_parser("update", help="アイテムフィールドを更新")
    u.add_argument("--item", type=int, required=True)
    u.add_argument("--field", required=True)
    u.add_argument("--value", required=True)

    args = p.parse_args()
    if args.cmd == "ref":      cmd_ref(args)
    elif args.cmd == "auction": cmd_auction(args)
    elif args.cmd == "fake":    cmd_fake(args)
    elif args.cmd == "update":  cmd_update(args)
    else:
        p.print_help()


if __name__ == "__main__":
    main()
