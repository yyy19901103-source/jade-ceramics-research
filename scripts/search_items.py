#!/usr/bin/env python3
"""Search items in the database with multiple filter conditions."""
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_connection


def search(
    keyword: str = None,
    category: str = None,
    material: str = None,
    period: str = None,
    price_min: float = None,
    price_max: float = None,
    max_risk: int = None,
    min_risk: int = None,
    seller: str = None,
    has_certificate: bool = None,
    returnable: bool = None,
    db_path=None,
) -> list[dict]:
    conn = get_connection(db_path) if db_path else get_connection()

    conditions = []
    params = []

    if keyword:
        conditions.append(
            "(i.name LIKE ? OR i.description LIKE ? OR i.material LIKE ? OR i.seller LIKE ?)"
        )
        like = f"%{keyword}%"
        params.extend([like, like, like, like])
    if category:
        conditions.append("i.category LIKE ?")
        params.append(f"%{category}%")
    if material:
        conditions.append("i.material LIKE ?")
        params.append(f"%{material}%")
    if period:
        conditions.append("i.estimated_period LIKE ?")
        params.append(f"%{period}%")
    if price_min is not None:
        conditions.append("i.price >= ?")
        params.append(price_min)
    if price_max is not None:
        conditions.append("i.price <= ?")
        params.append(price_max)
    if seller:
        conditions.append("i.seller LIKE ?")
        params.append(f"%{seller}%")
    if has_certificate is not None:
        conditions.append("i.has_certificate = ?")
        params.append(1 if has_certificate else 0)
    if returnable is not None:
        conditions.append("i.returnable = ?")
        params.append(1 if returnable else 0)
    if max_risk is not None:
        conditions.append("(a.calculated_score IS NULL OR a.calculated_score <= ?)")
        params.append(max_risk)
    if min_risk is not None:
        conditions.append("a.calculated_score >= ?")
        params.append(min_risk)

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = f"""
        SELECT i.*, a.calculated_score, a.risk_level, a.force_high_risk
        FROM items i
        LEFT JOIN authenticity_assessments a ON a.item_id = i.id
        {where}
        ORDER BY i.id DESC
    """
    rows = conn.execute(sql, params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def print_results(results: list[dict]):
    if not results:
        print("No results found.")
        return
    print(f"Found {len(results)} item(s):\n")
    risk_emoji = {"低リスク": "🟢", "注意": "🟡", "要警戒": "🟠", "高リスク": "🔴", "購入非推奨": "⛔"}
    for r in results:
        score = r.get("calculated_score")
        level = r.get("risk_level", "未評価")
        emoji = risk_emoji.get(level, "⚪")
        cert = "✓" if r.get("has_certificate") else "✗"
        ret = "可" if r.get("returnable") else "不可"
        price = f"{r['price']:,.0f}{r.get('currency','')}" if r.get("price") else "—"
        score_str = f"{score}点 {emoji} {level}" if score is not None else "未評価"
        print(f"  [{r['id']:>3}] {r['name']}")
        print(f"         分類:{r.get('category','—')}  材質:{r.get('material','—')}  年代:{r.get('estimated_period','—')}")
        print(f"         価格:{price}  鑑別書:{cert}  返品:{ret}")
        print(f"         リスク:{score_str}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Search the antiques database")
    parser.add_argument("-k", "--keyword",      help="Keyword (name/description/material/seller)")
    parser.add_argument("-c", "--category",     help="Category filter (partial match)")
    parser.add_argument("-m", "--material",     help="Material filter (partial match)")
    parser.add_argument("-p", "--period",       help="Period filter (partial match)")
    parser.add_argument("--price-min",          type=float, help="Minimum price")
    parser.add_argument("--price-max",          type=float, help="Maximum price")
    parser.add_argument("--risk-max",           type=int,   help="Maximum risk score (0-100)")
    parser.add_argument("--risk-min",           type=int,   help="Minimum risk score (0-100)")
    parser.add_argument("-s", "--seller",       help="Seller filter (partial match)")
    parser.add_argument("--has-cert",           action="store_true", default=None,
                        help="Filter: has certificate")
    parser.add_argument("--returnable",         action="store_true", default=None,
                        help="Filter: returnable items only")
    args = parser.parse_args()

    results = search(
        keyword=args.keyword,
        category=args.category,
        material=args.material,
        period=args.period,
        price_min=args.price_min,
        price_max=args.price_max,
        max_risk=args.risk_max,
        min_risk=args.risk_min,
        seller=args.seller,
        has_certificate=args.has_cert if args.has_cert else None,
        returnable=args.returnable if args.returnable else None,
    )
    print_results(results)


if __name__ == "__main__":
    main()
