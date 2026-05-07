#!/usr/bin/env python3
"""
Photo-upload purchase decision flow.

Accepts item info + photo observations from a JSON file (no DB required).
Runs BuyAgent → NoBuyAgent → JudgeAgent → outputs Markdown report.

Usage:
  python3 scripts/quick_judge.py <input.json>
  python3 scripts/quick_judge.py <input.json> --out reports/
  python3 scripts/quick_judge.py --template    # print JSON template

JSON input format:
  See --template output or docs/quick_judge_template.json
"""
import sys
import json
import argparse
import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.agents import (
    BuyAgent, NoBuyAgent, JudgeAgent,
    Reason, BuyResult, NoBuyResult,
    VERDICT_LABELS, CONSERVATIVE_CATEGORIES, CONSERVATIVE_KEYWORDS,
)

REPORTS_DIR = Path(__file__).parent.parent / "reports"

TEMPLATE = {
    "item": {
        "name": "商品名を入れる",
        "category": "翡翠 / 白玉 / 和田白玉 / 古玉 / 古陶磁 / 陶芸アンティーク / 芸術品",
        "material": "材質（例：ネフライト）",
        "estimated_period": "推定年代（例：清代）",
        "estimated_origin": "推定産地（例：新疆和田）",
        "size_description": "サイズ（例：縦8cm×横5cm）",
        "weight_g": 0,
        "price": 0,
        "currency": "JPY",
        "seller": "販売元名",
        "source_url": "https://...",
        "has_certificate": 0,
        "certificate_issuer": "",
        "returnable": 0,
        "description": "販売説明文（コピペ可）",
        "condition": "状態",
        "accessories": "付属品",
    },
    "photo_observations": {
        "color": "色の観察（例：薄い緑白色、均一）",
        "gloss": "艶の観察（例：温和な艶、過度な光沢なし）",
        "transparency": "透明感（例：半透明、透過光で内部構造確認可）",
        "wear": "摩耗・使用感（例：長期使用による自然な摩耗あり）",
        "damage": "傷・欠け（例：微小な傷あり、欠けなし）",
        "tool_marks": "工具痕（例：観察できず / 手彫り痕あり）",
        "surface": "表面状態（例：土沁あり、一部艶引け）",
        "bottom": "底面・高台（例：高台削りに個体差あり）",
        "other": "その他観察（自由記入）",
        "photos_available": ["正面", "背面"],
        "photos_missing": ["透過光", "UV", "拡大", "底面"]
    },
    "context": {
        "auction_comparisons": [
            {
                "auction_house": "例：クリスティーズ香港",
                "item_name": "類似品名",
                "period": "年代",
                "material": "材質",
                "hammer_price": 0,
                "currency": "HKD",
                "sale_date": "2024-01-01",
                "provenance": "来歴",
                "memo": "比較メモ"
            }
        ],
        "references": [
            {
                "title": "参考資料タイトル",
                "ref_type": "論文 / 博物館資料 / 鑑定機関資料",
                "reliability": 4,
                "key_points": "重要ポイント",
                "url": ""
            }
        ],
        "fake_feature_matches": [
            {
                "feature_name": "一致した偽物特徴名",
                "danger_level": 3,
                "match_confidence": "高 / 中 / 低",
                "notes": "具体的な一致箇所"
            }
        ]
    }
}


def build_item_from_json(d: dict) -> dict:
    item = d.get("item", {})
    # Ensure boolean-like fields
    item.setdefault("has_certificate", 0)
    item.setdefault("returnable", 0)
    item.setdefault("price", 0)
    return item


def build_assessment_from_json(d: dict, item: dict) -> dict:
    """
    Derive risk assessment flags from photo observations and item data.
    This is the key bridge: maps photo_observations → assessment flags.
    """
    obs   = d.get("photo_observations", {})
    ctx   = d.get("context", {})
    asmt  = {"_item_price": item.get("price", 0)}
    missing = [p.lower() for p in obs.get("photos_missing", [])]
    available = [p.lower() for p in obs.get("photos_available", [])]

    # Photo flags
    asmt["few_photos"]              = 1 if len(available) < 3 else 0
    asmt["front_only"]              = 1 if available == ["正面"] or available == ["front"] else 0
    asmt["no_transmitted_light"]    = 1 if any("透過" in m or "transmitted" in m for m in missing) else 0
    asmt["no_uv_photo"]             = 1 if any("uv" in m.lower() for m in missing) else 0
    asmt["no_side_bottom_closeup"]  = 1 if len(available) < 3 else 0
    asmt["sufficient_hq_photos"]    = 1 if len(available) >= 5 else 0
    asmt["has_special_photos"]      = 1 if any(p in ("透過光", "UV", "拡大") for p in obs.get("photos_available", [])) else 0

    # Gloss / color anomaly
    gloss = (obs.get("gloss") or "").lower()
    color = (obs.get("color") or "").lower()
    asmt["unnatural_gloss"]     = 1 if any(w in gloss for w in ("過度", "不自然", "強すぎ", "ガラス")) else 0
    asmt["too_uniform_color"]   = 1 if any(w in color for w in ("均一すぎ", "均一", "不自然")) else 0

    # Certificate
    asmt["no_certificate"]      = 0 if item.get("has_certificate") else 1
    asmt["expensive_no_cert"]   = 1 if (item.get("price", 0) or 0) > 100000 and not item.get("has_certificate") else 0

    # Return
    asmt["no_return"]           = 0 if item.get("returnable") else 1

    # Provenance
    desc = (item.get("description") or "").lower()
    asmt["no_provenance"]       = 1 if not any(w in desc for w in ("来歴", "旧蔵", "コレクション", "入手")) else 0
    asmt["no_source_url"]       = 0 if item.get("source_url") else 1

    # Provenance
    asmt["ancient_no_provenance"] = 1 if (
        any(w in (item.get("name","") + desc) for w in ("古玉","漢代","戦国","周代","商代"))
        and not any(w in desc for w in ("来歴","旧蔵","コレクション"))
    ) else 0
    asmt["excavated_no_legality"] = 1 if "出土" in (item.get("name","") + desc) and "来歴" not in desc else 0

    # Inflate keywords
    asmt["strong_selling_keywords"] = 1 if any(
        w in (item.get("name","") + desc) for w in ("羊脂","宮廷","漢代","戦国","真品","出土","希少")
    ) else 0

    # Auction comparison
    auction_data = ctx.get("auction_comparisons", [])
    if auction_data and item.get("price"):
        hammers = [a.get("hammer_price", 0) for a in auction_data if a.get("hammer_price")]
        if hammers:
            avg = sum(hammers) / len(hammers)
            # Note: different currencies not converted — user should normalize
            asmt["below_market_price"] = 1 if item["price"] < avg * 0.5 else 0
            asmt["expensive_no_evidence"] = 1 if item["price"] > avg * 2 and not item.get("has_certificate") else 0

    # Reductions
    refs = ctx.get("references", [])
    high_refs = [r for r in refs if r.get("reliability", 0) >= 5]
    asmt["museum_publication"]      = 1 if any(r.get("ref_type","") in ("博物館資料","論文") for r in high_refs) else 0
    asmt["has_reliable_certificate"] = 1 if item.get("has_certificate") else 0
    asmt["has_return_guarantee"]    = 1 if item.get("returnable") else 0
    asmt["clear_provenance"]        = 1 if any(w in desc for w in ("来歴","旧蔵","コレクション")) else 0

    # Fake feature matches → processing flags
    fakes = ctx.get("fake_feature_matches", [])
    for ff in fakes:
        name_lower = (ff.get("feature_name") or "").lower()
        if "樹脂" in name_lower or "b貨" in name_lower:
            asmt["resin_suspected"] = 1
        if "染色" in name_lower or "c貨" in name_lower:
            asmt["dyeing_suspected"] = 1
        if "人工土沁" in name_lower or "仿古" in name_lower:
            asmt["antique_fake_suspected"] = 1
            asmt["artificial_soil_suspected"] = 1
        if "流用" in name_lower or "写真" in name_lower:
            asmt["photo_reuse_suspected"] = 1
        if "酸" in name_lower:
            asmt["acid_suspected"] = 1

    return asmt


def build_fakes_from_json(d: dict) -> list[dict]:
    return [
        {
            "feature_name": f.get("feature_name", ""),
            "danger_level": f.get("danger_level", 3),
            "match_confidence": f.get("match_confidence", "不明"),
            "notes": f.get("notes", ""),
            "target_category": "",
            "description": "",
            "observation_method": "",
            "judgment_basis": "",
        }
        for f in d.get("context", {}).get("fake_feature_matches", [])
    ]


def build_auctions_from_json(d: dict) -> list[dict]:
    return [
        {
            "auction_house": a.get("auction_house", ""),
            "lot_number": a.get("lot_number", ""),
            "item_name": a.get("item_name", ""),
            "period": a.get("period", ""),
            "material": a.get("material", ""),
            "size_description": a.get("size_description", ""),
            "hammer_price": a.get("hammer_price"),
            "currency": a.get("currency", "JPY"),
            "sale_date": a.get("sale_date", ""),
            "provenance": a.get("provenance", ""),
            "condition_description": a.get("condition_description", ""),
            "source_url": a.get("url", ""),
            "comparison_notes": a.get("memo", ""),
        }
        for a in d.get("context", {}).get("auction_comparisons", [])
    ]


def build_refs_from_json(d: dict) -> list[dict]:
    return [
        {
            "title": r.get("title", ""),
            "ref_type": r.get("ref_type", ""),
            "reliability": r.get("reliability", 3),
            "key_points": r.get("key_points", ""),
            "url": r.get("url", ""),
            "author": r.get("author", ""),
            "year": r.get("year"),
            "summary": r.get("summary", ""),
        }
        for r in d.get("context", {}).get("references", [])
    ]


def generate_quick_report(input_path: Path, out_dir: Path = REPORTS_DIR) -> Path:
    data = json.loads(input_path.read_text(encoding="utf-8"))

    item      = build_item_from_json(data)
    assessment = build_assessment_from_json(data, item)
    images    = []   # no DB images — photo observations are in photo_observations
    fakes     = build_fakes_from_json(data)
    auctions  = build_auctions_from_json(data)
    refs      = build_refs_from_json(data)
    obs       = data.get("photo_observations", {})

    buy   = BuyAgent().analyze(item, assessment, images, refs, fakes, auctions)
    nobuy = NoBuyAgent().analyze(item, assessment, images, refs, fakes, auctions)
    judge = JudgeAgent().decide(buy, nobuy, item, assessment, auctions)

    today = datetime.date.today().isoformat()
    now   = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    verdict_label = VERDICT_LABELS.get(judge.verdict, judge.verdict)
    verdict_emoji = {
        "buy":            "🟢",
        "watch":          "🟡",
        "need_more_info": "🔵",
        "no_buy":         "🔴",
        "no_buy_strong":  "⛔",
    }.get(judge.verdict, "⚪")

    strength = "弱"
    if judge.evidence_score >= 4.0:
        strength = "強"
    elif judge.evidence_score >= 3.0:
        strength = "中"

    # Price validity
    price_str = f"{item.get('price', 0):,.0f} {item.get('currency','JPY')}" if item.get("price") else "—"
    price_validity = "—"
    if auctions:
        hammers = [a.get("hammer_price", 0) for a in auctions if a.get("hammer_price")]
        if hammers and item.get("price"):
            avg = sum(hammers) / len(hammers)
            ratio = item["price"] / avg
            price_validity = f"落札均価比 {ratio:.1%}（{'割安' if ratio < 0.8 else '適正' if ratio < 1.3 else '割高'}）※通貨換算注意"

    lines: list[str] = []
    a = lines.append

    a(f"# 購入判断レポート：{item.get('name','（無題）')}")
    a(f"\n生成日：{today}　｜　入力ファイル：{input_path.name}")
    a("")

    # 1. 結論
    a("---")
    a("## 1. 結論")
    a("")
    a(f"- **最終判断：** {verdict_emoji} **{verdict_label}**")
    a(f"- **推奨行動：** {judge.action}")
    a(f"- **判断の強さ：** {strength}（根拠強度 {judge.evidence_score:.1f}/5）")
    a(f"- **情報不足率：** {judge.info_shortage_rate:.0%}")
    if buy.reasons:
        a(f"- **主な買う理由：** {buy.reasons[0].text}")
    if nobuy.reasons:
        a(f"- **主な買わない理由：** {nobuy.reasons[0].text}")
    a("")
    if judge.forced_conservative:
        a("> ⚠️ このカテゴリ・キーワードは保守的判断対象（古玉・翡翠・羊脂・出土品等）です。")
        a("")

    # 2. 対象品概要
    a("---")
    a("## 2. 対象品概要")
    a("")
    cert = "あり（" + item.get("certificate_issuer","") + "）" if item.get("has_certificate") else "なし"
    ret  = "可" if item.get("returnable") else "不可"
    a(f"- **分類：** {item.get('category','—')}")
    a(f"- **材質：** {item.get('material','—')}")
    a(f"- **推定年代：** {item.get('estimated_period','—')}")
    a(f"- **推定産地：** {item.get('estimated_origin','—')}")
    a(f"- **サイズ：** {item.get('size_description','—')}")
    a(f"- **重量：** {str(item.get('weight_g',''))+'g' if item.get('weight_g') else '—'}")
    a(f"- **価格：** {price_str}")
    a(f"- **販売元：** {item.get('seller','—')}")
    a(f"- **URL：** {item.get('source_url','—')}")
    a(f"- **鑑別書：** {cert}")
    a(f"- **返品可否：** {ret}")
    a("")

    # 3. 写真から確認できる事実
    a("---")
    a("## 3. 写真から確認できる事実")
    a("")
    photo_fields = [
        ("色", "color"), ("艶", "gloss"), ("透明感", "transparency"),
        ("摩耗", "wear"), ("傷・欠け", "damage"), ("工具痕", "tool_marks"),
        ("表面状態", "surface"), ("底面・高台", "bottom"), ("その他", "other"),
    ]
    for label, key in photo_fields:
        val = obs.get(key, "")
        if val:
            a(f"- **{label}：** {val}")
    a("")
    available = obs.get("photos_available", [])
    missing   = obs.get("photos_missing", [])
    if available:
        a(f"- **確認済み写真：** {', '.join(available)}")
    if missing:
        a(f"- **不足写真：** {', '.join(missing)}")
    a("")

    # 説明文
    desc = item.get("description", "")
    if desc:
        a("**販売説明文：**")
        a("")
        a(f"> {desc}")
        a("")

    # 4. Buy Agent
    a("---")
    a("## 4. Buy Agent 判断")
    a("")
    a(f"- **結論：** {buy.conclusion}（根拠強度 {buy.overall_strength:.1f}/5）")
    a("")
    a("- **買う理由：**")
    if buy.reasons:
        for i, r in enumerate(buy.reasons, 1):
            fact_tag = {"fact": "【事実】", "inference": "【推定】", "hypothesis": "【仮説】"}.get(r.fact_type, "")
            a(f"  {i}. {fact_tag}{r.text}")
            a(f"     - 根拠：{r.evidence_source}（強度 {r.evidence_strength}/5）")
    else:
        a("  （積極的な買う根拠なし）")
    a("")
    if buy.conditions:
        a("- **買う場合の条件：**")
        for c in buy.conditions:
            a(f"  - {c}")
        a("")
    if buy.weak_points:
        a("- **弱い点：**")
        for w in buy.weak_points:
            a(f"  - {w}")
        a("")

    # 5. No-Buy Agent
    a("---")
    a("## 5. No-Buy Agent 判断")
    a("")
    a(f"- **結論：** {nobuy.conclusion}（根拠強度 {nobuy.overall_strength:.1f}/5）")
    a("")
    a("- **買わない理由：**")
    if nobuy.reasons:
        for i, r in enumerate(nobuy.reasons, 1):
            fact_tag = {"fact": "【事実】", "inference": "【推定】", "hypothesis": "【仮説】"}.get(r.fact_type, "")
            a(f"  {i}. {fact_tag}{r.text}")
            a(f"     - 根拠：{r.evidence_source}（強度 {r.evidence_strength}/5）")
    else:
        a("  （強い買わない根拠なし）")
    a("")
    if nobuy.info_gaps:
        a("- **追加確認事項：**")
        for ig in nobuy.info_gaps:
            a(f"  - [ ] {ig}")
        a("")

    # 6. Judge Agent
    a("---")
    a("## 6. Judge Agent 最終判断")
    a("")
    a(f"- **最終判断：** {verdict_emoji} {verdict_label}")
    a(f"- **根拠強度：** {judge.evidence_score:.1f}/5（{strength}）")
    a(f"- **情報不足率：** {judge.info_shortage_rate:.0%}")
    a(f"- **価格妥当性：** {price_validity}")
    if nobuy.risks:
        a(f"- **リスク：** {' / '.join(nobuy.risks)}")
    a(f"- **推奨行動：** {judge.action}")
    a("")
    if judge.additional_checks:
        a("- **追加確認事項：**")
        for ck in judge.additional_checks:
            a(f"  - [ ] {ck}")
        a("")
    a(f"**コメント：** {judge.comment}")
    a("")

    # 7. 購入判断
    a("---")
    a("## 7. 購入判断")
    a("")
    purchase_map = {
        "buy":            "🟢 購入候補",
        "watch":          "🟡 様子見 / 追加確認後に検討",
        "need_more_info": "🔵 追加情報が必要",
        "no_buy":         "🔴 購入しない",
        "no_buy_strong":  "⛔ 購入非推奨",
    }
    a(f"**{purchase_map.get(judge.verdict, verdict_label)}**")
    a("")

    # 8. 反省欄
    a("---")
    a("## 反省欄")
    a("")
    a("*（購入後、実際の結果が判明したら記入してください）*")
    a("")
    a("- **実際の結果：** （未記入）")
    a("- **判断ミスの有無：** （未記入）")
    a("- **見落とした根拠：** （未記入）")
    a("- **次回改善案：** （未記入）")
    a("")
    a("---")
    a(f"*本レポートは購入判断支援用です。真贋の断定ではありません。写真観察は事実、材質・年代は推定、偽物可能性は仮説として扱っています。*")
    a(f"*生成日時：{now}*")

    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in (item.get("name") or "item"))
    out_path = out_dir / f"quick_judgment_{safe}_{today}.md"
    out_path.write_text("\n".join(lines), encoding="utf-8")
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Photo-upload purchase decision flow")
    parser.add_argument("input_json", nargs="?", help="Input JSON file")
    parser.add_argument("--template", action="store_true", help="Print JSON template and exit")
    parser.add_argument("--out", default=str(REPORTS_DIR), help="Output directory")
    args = parser.parse_args()

    if args.template:
        print(json.dumps(TEMPLATE, ensure_ascii=False, indent=2))
        return

    if not args.input_json:
        parser.print_help()
        sys.exit(1)

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    path = generate_quick_report(Path(args.input_json), out_dir=out_dir)
    print(f"Quick judgment report saved: {path}")


if __name__ == "__main__":
    main()
