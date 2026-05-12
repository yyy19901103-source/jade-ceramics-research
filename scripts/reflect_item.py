#!/usr/bin/env python3
"""
Record actual outcome and run ReflectionAgent on a judged item.

Usage:
  python3 scripts/reflect_item.py <item_id> <outcome>

Outcome codes:
  genuine        本物だった
  fake           偽物だった
  treated        処理品だった
  overpriced     高すぎた
  good_purchase  良い買い物だった
  bad_purchase   悪い買い物だった
  no_buy_correct 買わなくて正解だった
  unknown        判断不能
"""
import sys
import json
import argparse
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.db import get_connection, dict_from_row
from src.agents import (
    BuyAgent, NoBuyAgent, JudgeAgent, ReflectionAgent,
    BuyResult, NoBuyResult, JudgeResult, Reason,
    OUTCOME_LABELS, VERDICT_LABELS,
)

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)


def _load_judgment(item_id: int, conn) -> dict | None:
    row = conn.execute(
        "SELECT * FROM judgment_results WHERE item_id=? ORDER BY id DESC LIMIT 1",
        (item_id,),
    ).fetchone()
    return dict(row) if row else None


def _reconstruct_buy(jrow: dict) -> BuyResult:
    b = BuyResult()
    b.conclusion = jrow.get("buy_conclusion", "")
    raw = json.loads(jrow.get("buy_reasons") or "[]")
    b.reasons = [Reason(text=r["text"], evidence_source="", evidence_strength=r.get("strength", 1), fact_type="fact") for r in raw]
    b.conditions = json.loads(jrow.get("buy_conditions") or "[]")
    b.weak_points = json.loads(jrow.get("buy_weak_points") or "[]")
    b.overall_strength = sum(r.evidence_strength for r in b.reasons) / max(len(b.reasons), 1)
    return b


def _reconstruct_nobuy(jrow: dict) -> NoBuyResult:
    n = NoBuyResult()
    n.conclusion = jrow.get("nobuy_conclusion", "")
    raw = json.loads(jrow.get("nobuy_reasons") or "[]")
    n.reasons = [Reason(text=r["text"], evidence_source="", evidence_strength=r.get("strength", 1), fact_type="fact") for r in raw]
    n.risks = json.loads(jrow.get("nobuy_risks") or "[]")
    n.info_gaps = json.loads(jrow.get("nobuy_info_gaps") or "[]")
    n.overall_strength = sum(r.evidence_strength for r in n.reasons) / max(len(n.reasons), 1)
    return n


def _reconstruct_judge(jrow: dict) -> JudgeResult:
    j = JudgeResult()
    j.verdict = jrow.get("judge_verdict", "need_more_info")
    j.action = jrow.get("judge_action", "")
    j.comment = jrow.get("judge_comment", "")
    j.evidence_score = jrow.get("evidence_score", 0.0) or 0.0
    j.info_shortage_rate = jrow.get("info_shortage_rate", 0.0) or 0.0
    j.buy_valid = json.loads(jrow.get("judge_buy_valid") or "[]")
    j.nobuy_valid = json.loads(jrow.get("judge_nobuy_valid") or "[]")
    j.additional_checks = json.loads(jrow.get("additional_checks") or "[]")
    return j


def run_reflection(item_id: int, actual_outcome: str) -> Path:
    conn = get_connection()
    item = dict_from_row(conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())
    if not item:
        raise ValueError(f"Item {item_id} not found")

    jrow = _load_judgment(item_id, conn)
    if jrow:
        buy   = _reconstruct_buy(jrow)
        nobuy = _reconstruct_nobuy(jrow)
        judge = _reconstruct_judge(jrow)
    else:
        # No saved judgment — run agents fresh to reflect
        from src.risk_score import calculate
        a_row = conn.execute("SELECT * FROM authenticity_assessments WHERE item_id=?", (item_id,)).fetchone()
        assessment = dict(a_row) if a_row else {}
        if assessment:
            assessment["_item_price"] = item.get("price", 0)
            assessment = calculate(assessment)
        images  = [dict(r) for r in conn.execute("SELECT * FROM images WHERE item_id=?", (item_id,)).fetchall()]
        refs    = [dict(r) for r in conn.execute("""SELECT r.* FROM references_ r JOIN item_references ir ON ir.reference_id=r.id WHERE ir.item_id=?""", (item_id,)).fetchall()]
        fakes   = [dict(r) for r in conn.execute("""SELECT ff.*, iff.match_confidence FROM fake_features ff JOIN item_fake_features iff ON iff.fake_feature_id=ff.id WHERE iff.item_id=?""", (item_id,)).fetchall()]
        auctions = [dict(r) for r in conn.execute("""SELECT a.* FROM auctions a JOIN item_auctions ia ON ia.auction_id=a.id WHERE ia.item_id=?""", (item_id,)).fetchall()]
        buy   = BuyAgent().analyze(item, assessment, images, refs, fakes, auctions)
        nobuy = NoBuyAgent().analyze(item, assessment, images, refs, fakes, auctions)
        judge = JudgeAgent().decide(buy, nobuy, item, assessment, auctions)

    reflection = ReflectionAgent().reflect(buy, nobuy, judge, actual_outcome)

    outcome_label = OUTCOME_LABELS.get(actual_outcome, actual_outcome)
    verdict_label = VERDICT_LABELS.get(judge.verdict, judge.verdict)
    today = datetime.date.today().isoformat()
    now   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines: list[str] = []
    a = lines.append

    a(f"# 後日反省レポート：{item['name']}")
    a(f"\n記録日：{today}　｜　Item ID：{item_id}")
    a("")

    a("---")
    a("## 実際の結果")
    a("")
    result_emoji = {
        "genuine": "✅", "good_purchase": "✅", "no_buy_correct": "✅",
        "fake": "❌", "treated": "⚠️", "overpriced": "⚠️",
        "bad_purchase": "❌", "unknown": "❓",
    }.get(actual_outcome, "❓")
    a(f"**{result_emoji} {outcome_label}**（コード：`{actual_outcome}`）")
    a("")
    a("（事実・推定・追記情報は下記に記載してください）")
    a("")

    a("---")
    a("## 当初の判断")
    a("")
    a(f"- **当初の判断：** {verdict_label}")
    a(f"- **根拠強度スコア：** {judge.evidence_score:.1f}/5")
    a(f"- **情報不足率：** {judge.info_shortage_rate:.0%}")
    a("")

    a("---")
    a("## 判断ミスの有無")
    a("")
    if reflection.has_error:
        a("**⚠️ 判断ミスあり**")
    else:
        a("**✅ 判断ミスなし（または判断不能）**")
    a("")

    a("---")
    a("## 弱かったエージェント")
    a("")
    if reflection.weak_agents:
        for w in reflection.weak_agents:
            a(f"- {w}")
    else:
        a("- 特記なし")
    a("")

    a("---")
    a("## 見落とした根拠")
    a("")
    if reflection.missed_evidence:
        for m in reflection.missed_evidence:
            a(f"- {m}")
    else:
        a("- 見落としは確認されなかった")
    a("")

    a("---")
    a("## 根拠の重み付けの問題")
    a("")
    if reflection.weight_problems:
        for wp in reflection.weight_problems:
            a(f"- {wp}")
    else:
        a("- 特記なし")
    a("")

    a("---")
    a("## 次回追加すべき確認項目")
    a("")
    if reflection.next_checks:
        for nc in reflection.next_checks:
            a(f"- [ ] {nc}")
    else:
        a("- 特記なし")
    a("")

    a("---")
    a("## 判断ルールの改善案")
    a("")
    a("*（改善案は提案のみ。ルールは人間が更新すること）*")
    a("")
    if reflection.rule_improvements:
        for ri in reflection.rule_improvements:
            a(f"- {ri}")
    else:
        a("- 特記なし")
    a("")

    a("---")
    a("## 当初のBuy Agent 主張（参考）")
    a("")
    if buy.reasons:
        for r in buy.reasons:
            a(f"- {r.text}（根拠強度 {r.evidence_strength}/5）")
    else:
        a("- なし")
    a("")

    a("---")
    a("## 当初のNo-Buy Agent 主張（参考）")
    a("")
    if nobuy.reasons:
        for r in nobuy.reasons:
            a(f"- {r.text}（根拠強度 {r.evidence_strength}/5）")
    else:
        a("- なし")
    a("")

    a("---")
    a(f"*生成日時：{now}*")

    # Update DB
    if jrow:
        conn.execute(
            "UPDATE judgment_results SET actual_outcome=?, reflection_json=?, updated_at=CURRENT_TIMESTAMP WHERE id=?",
            (
                actual_outcome,
                json.dumps({
                    "has_error": reflection.has_error,
                    "weak_agents": reflection.weak_agents,
                    "missed_evidence": reflection.missed_evidence,
                    "weight_problems": reflection.weight_problems,
                    "next_checks": reflection.next_checks,
                    "rule_improvements": reflection.rule_improvements,
                }, ensure_ascii=False),
                jrow["id"],
            ),
        )
        conn.commit()

    conn.close()

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in item["name"])
    out_path = REPORTS_DIR / f"reflection_{item_id}_{safe}_{today}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Record actual outcome and run ReflectionAgent")
    parser.add_argument("item_id", type=int, help="Item ID")
    parser.add_argument(
        "outcome",
        choices=list(OUTCOME_LABELS.keys()),
        help="Actual outcome code",
    )
    args = parser.parse_args()

    path = run_reflection(args.item_id, args.outcome)
    print(f"Reflection report saved: {path}")


if __name__ == "__main__":
    main()
