#!/usr/bin/env python3
"""
Run the 4-agent purchase decision system on a database item.

Usage:
  python3 scripts/judge_item.py <item_id>
  python3 scripts/judge_item.py <item_id> --save   # save to DB
  python3 scripts/judge_item.py <item_id> --out reports/  # custom output dir
"""
import sys
import json
import argparse
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_connection, dict_from_row
from src.risk_score import calculate
from src.agents import (
    BuyAgent, NoBuyAgent, JudgeAgent,
    VERDICT_LABELS,
    buy_result_to_dict, nobuy_result_to_dict, judge_result_to_dict,
)

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def load_item_data(item_id: int, conn):
    item = dict_from_row(conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())
    if not item:
        raise ValueError(f"Item {item_id} not found")

    a_row = conn.execute(
        "SELECT * FROM authenticity_assessments WHERE item_id=?", (item_id,)
    ).fetchone()
    assessment = dict(a_row) if a_row else {}
    if assessment:
        assessment["_item_price"] = item.get("price", 0)
        assessment = calculate(assessment)

    images = [dict(r) for r in conn.execute(
        "SELECT * FROM images WHERE item_id=?", (item_id,)
    ).fetchall()]

    refs = [dict(r) for r in conn.execute(
        """SELECT r.* FROM references_ r
           JOIN item_references ir ON ir.reference_id=r.id
           WHERE ir.item_id=?""", (item_id,)
    ).fetchall()]

    fakes = [dict(r) for r in conn.execute(
        """SELECT ff.*, iff.match_confidence, iff.notes AS match_notes
           FROM fake_features ff
           JOIN item_fake_features iff ON iff.fake_feature_id=ff.id
           WHERE iff.item_id=?""", (item_id,)
    ).fetchall()]

    auctions = [dict(r) for r in conn.execute(
        """SELECT a.*, ia.comparison_notes
           FROM auctions a
           JOIN item_auctions ia ON ia.auction_id=a.id
           WHERE ia.item_id=?""", (item_id,)
    ).fetchall()]

    return item, assessment, images, refs, fakes, auctions


def generate_report(item_id: int, save_to_db: bool = False, out_dir: Path = REPORTS_DIR) -> Path:
    conn = get_connection()
    item, assessment, images, refs, fakes, auctions = load_item_data(item_id, conn)

    # Run agents
    buy_agent   = BuyAgent()
    nobuy_agent = NoBuyAgent()
    judge_agent = JudgeAgent()

    buy   = buy_agent.analyze(item, assessment, images, refs, fakes, auctions)
    nobuy = nobuy_agent.analyze(item, assessment, images, refs, fakes, auctions)
    judge = judge_agent.decide(buy, nobuy, item, assessment, auctions)

    today = datetime.date.today().isoformat()
    now   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Verdict display
    verdict_label = VERDICT_LABELS.get(judge.verdict, judge.verdict)
    verdict_emoji = {
        "buy":            "🟢",
        "watch":          "🟡",
        "need_more_info": "🔵",
        "no_buy":         "🔴",
        "no_buy_strong":  "⛔",
    }.get(judge.verdict, "⚪")

    strength_label = {
        (4.0, 5.1): "強",
        (3.0, 4.0): "中",
        (0.0, 3.0): "弱",
    }
    strength = "弱"
    for (lo, hi), label in strength_label.items():
        if lo <= judge.evidence_score < hi:
            strength = label
            break

    lines: list[str] = []
    a = lines.append

    a(f"# 購入判断レポート：{item['name']}")
    a(f"\n生成日：{today}　｜　Item ID：{item_id}")
    a("")

    # -------------------------------------------------------------------
    a("---")
    a("## 1. 結論")
    a("")
    a(f"- **最終判断：** {verdict_emoji} **{verdict_label}**")
    a(f"- **推奨行動：** {judge.action}")
    a(f"- **判断の強さ：** {strength}（根拠強度スコア {judge.evidence_score:.1f}/5）")
    a(f"- **情報不足率：** {judge.info_shortage_rate:.0%}")
    if buy.reasons:
        a(f"- **主な買う理由：** {buy.reasons[0].text}")
    if nobuy.reasons:
        a(f"- **主な買わない理由：** {nobuy.reasons[0].text}")
    a("")
    if judge.forced_conservative:
        a("> ⚠️ このカテゴリ・キーワードは保守的判断対象です。")
        a("")

    # -------------------------------------------------------------------
    a("---")
    a("## 2. 対象品の概要")
    a("")
    cert = "あり（" + item.get("certificate_issuer", "") + "）" if item.get("has_certificate") else "なし"
    ret  = "可" if item.get("returnable") else "不可"
    price_str = f"{item['price']:,.0f} {item.get('currency','JPY')}" if item.get("price") else "—"
    a(f"- **名称：** {item['name']}")
    a(f"- **分類：** {item.get('category','—')}")
    a(f"- **材質：** {item.get('material','—')}")
    a(f"- **推定年代：** {item.get('estimated_period','—')}")
    a(f"- **推定産地：** {item.get('estimated_origin','—')}")
    a(f"- **サイズ：** {item.get('size_description','—')}")
    a(f"- **重量：** {str(item.get('weight_g','—'))+'g' if item.get('weight_g') else '—'}")
    a(f"- **価格：** {price_str}")
    a(f"- **販売元：** {item.get('seller','—')}")
    a(f"- **鑑別書：** {cert}")
    a(f"- **返品：** {ret}")
    a(f"- **URL：** {item.get('source_url','—')}")
    a(f"- **取得日：** {item.get('acquired_date','—')}")
    a("")

    # -------------------------------------------------------------------
    a("---")
    a("## 3. 観察事実")
    a("")
    a("### 写真から確認できる事実")
    a("")
    if images:
        photo_types = [img.get("image_type", "不明") for img in images]
        a(f"- 写真種別：{', '.join(photo_types)}")
        a(f"- 写真枚数：{len(images)}枚")
        for img in images:
            if img.get("memo"):
                a(f"  - {img['image_type']}：{img['memo']}")
    else:
        a("- 画像データなし")
    a("")
    a("### 説明文から確認できる事実")
    a("")
    desc = item.get("description", "")
    if desc:
        a(f"> {desc}")
    else:
        a("- 説明文なし")
    a("")
    a("### 資料から確認できる事実")
    a("")
    if refs:
        for ref in refs:
            a(f"- 【{ref.get('ref_type','資料')}】{ref['title']}（{ref.get('year','')}）")
            if ref.get("key_points"):
                a(f"  - 重要ポイント：{ref['key_points']}")
    else:
        a("- 関連資料なし")
    a("")

    # -------------------------------------------------------------------
    a("---")
    a("## 4. Buy Agent 判断")
    a("")
    a(f"- **結論：** {buy.conclusion}")
    a(f"- **根拠強度平均：** {buy.overall_strength:.1f}/5")
    a("")
    a("- **買う理由：**")
    if buy.reasons:
        for i, r in enumerate(buy.reasons, 1):
            fact_tag = {"fact": "【事実】", "inference": "【推定】", "hypothesis": "【仮説】"}.get(r.fact_type, "")
            a(f"  {i}. {fact_tag}{r.text}")
            a(f"     - 根拠：{r.evidence_source}（強度 {r.evidence_strength}/5）")
    else:
        a("  （なし）")
    a("")
    if buy.weak_points:
        a("- **弱い点：**")
        for w in buy.weak_points:
            a(f"  - {w}")
        a("")
    if buy.conditions:
        a("- **買う場合の条件：**")
        for c in buy.conditions:
            a(f"  - {c}")
        a("")

    # -------------------------------------------------------------------
    a("---")
    a("## 5. No-Buy Agent 判断")
    a("")
    a(f"- **結論：** {nobuy.conclusion}")
    a(f"- **根拠強度平均：** {nobuy.overall_strength:.1f}/5")
    a("")
    a("- **買わない理由：**")
    if nobuy.reasons:
        for i, r in enumerate(nobuy.reasons, 1):
            fact_tag = {"fact": "【事実】", "inference": "【推定】", "hypothesis": "【仮説】"}.get(r.fact_type, "")
            a(f"  {i}. {fact_tag}{r.text}")
            a(f"     - 根拠：{r.evidence_source}（強度 {r.evidence_strength}/5）")
    else:
        a("  （なし）")
    a("")
    if nobuy.risks:
        a("- **主なリスク：**")
        for rk in nobuy.risks:
            a(f"  - {rk}")
        a("")
    if nobuy.info_gaps:
        a("- **情報不足：**")
        for ig in nobuy.info_gaps:
            a(f"  - {ig}")
        a("")

    # -------------------------------------------------------------------
    a("---")
    a("## 6. Judge Agent 最終判断")
    a("")
    a(f"- **最終判断：** {verdict_emoji} {verdict_label}")
    a(f"- **推奨行動：** {judge.action}")
    a("")
    if judge.buy_valid:
        a("- **Buy Agent の有効な主張：**")
        for v in judge.buy_valid:
            a(f"  - ✅ {v}")
        a("")
    if judge.nobuy_valid:
        a("- **No-Buy Agent の有効な主張：**")
        for v in judge.nobuy_valid:
            a(f"  - ⚠️ {v}")
        a("")
    a(f"- **根拠強度評価：** {judge.evidence_score:.1f}/5（{strength}）")
    a(f"- **情報不足率：** {judge.info_shortage_rate:.0%}")
    a("")
    if judge.additional_checks:
        a("- **追加確認すべき内容：**")
        for ck in judge.additional_checks:
            a(f"  - [ ] {ck}")
        a("")
    a(f"- **最終コメント：** {judge.comment}")
    a("")

    # -------------------------------------------------------------------
    a("---")
    a("## 7. 購入判断")
    a("")
    purchase_map = {
        "buy":            "🟢 購入候補",
        "watch":          "🟡 追加確認後に検討 / 様子見",
        "need_more_info": "🔵 追加情報が必要",
        "no_buy":         "🔴 購入しない",
        "no_buy_strong":  "⛔ 購入非推奨",
    }
    a(f"**{purchase_map.get(judge.verdict, verdict_label)}**")
    a("")

    # -------------------------------------------------------------------
    a("---")
    a("## 8. 後日反省欄")
    a("")
    a("*（購入後、実際の結果が判明したら `python3 scripts/reflect_item.py` で記入する）*")
    a("")
    a("### 実際の結果")
    a("- （未記入）")
    a("")
    a("### 判断ミスの有無")
    a("- （未記入）")
    a("")
    a("### 弱かったエージェント")
    a("- （未記入）")
    a("")
    a("### 見落とした根拠")
    a("- （未記入）")
    a("")
    a("### 判断基準の問題")
    a("- （未記入）")
    a("")
    a("### 次回の改善案")
    a("- （未記入）")
    a("")
    a("### ルール更新提案")
    a("- （未記入）")
    a("")
    a("---")
    a(f"*本レポートは購入判断支援用です。真贋の断定ではありません。*")
    a(f"*生成日時：{now}*")

    # Save to DB
    if save_to_db:
        conn.execute("""
            INSERT INTO judgment_results
              (item_id, buy_conclusion, buy_reasons, buy_conditions, buy_weak_points,
               nobuy_conclusion, nobuy_reasons, nobuy_risks, nobuy_info_gaps,
               judge_verdict, judge_action, judge_comment,
               evidence_score, info_shortage_rate,
               judge_buy_valid, judge_nobuy_valid, additional_checks)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            item_id,
            buy.conclusion,
            json.dumps([{"text": r.text, "strength": r.evidence_strength} for r in buy.reasons], ensure_ascii=False),
            json.dumps(buy.conditions, ensure_ascii=False),
            json.dumps(buy.weak_points, ensure_ascii=False),
            nobuy.conclusion,
            json.dumps([{"text": r.text, "strength": r.evidence_strength} for r in nobuy.reasons], ensure_ascii=False),
            json.dumps(nobuy.risks, ensure_ascii=False),
            json.dumps(nobuy.info_gaps, ensure_ascii=False),
            judge.verdict,
            judge.action,
            judge.comment,
            judge.evidence_score,
            judge.info_shortage_rate,
            json.dumps(judge.buy_valid, ensure_ascii=False),
            json.dumps(judge.nobuy_valid, ensure_ascii=False),
            json.dumps(judge.additional_checks, ensure_ascii=False),
        ))
        conn.commit()

    conn.close()

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in item["name"])
    out_path = out_dir / f"judgment_{item_id}_{safe}_{today}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Run 4-agent purchase judgment on an item")
    parser.add_argument("item_id", type=int, help="Item ID to judge")
    parser.add_argument("--save", action="store_true", help="Save judgment to database")
    parser.add_argument("--out", default=str(REPORTS_DIR), help="Output directory for report")
    args = parser.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    path = generate_report(args.item_id, save_to_db=args.save, out_dir=out_dir)
    print(f"Judgment report saved: {path}")


if __name__ == "__main__":
    main()
