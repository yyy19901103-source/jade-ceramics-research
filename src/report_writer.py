"""Generate Markdown authenticity/risk report for a single item."""
from __future__ import annotations
import datetime
from pathlib import Path
from src.db import get_connection, dict_from_row
from src.risk_score import RISK_POINTS, REDUCTION_POINTS, calculate

REPORTS_DIR = Path(__file__).parent.parent / "reports"
REPORTS_DIR.mkdir(exist_ok=True)

_RISK_EMOJI = {
    "低リスク": "🟢",
    "注意": "🟡",
    "要警戒": "🟠",
    "高リスク": "🔴",
    "購入非推奨": "⛔",
}

_JP_LABELS: dict[str, str] = {
    # リスク加点
    "no_certificate":               "鑑別書なし",
    "expensive_no_cert":            "高額品で鑑別書なし",
    "unknown_cert_issuer":          "鑑別書発行機関が不明",
    "unclear_cert_image":           "鑑別書画像が不鮮明",
    "cert_item_mismatch":           "鑑別書と商品の対応不明",
    "no_provenance":                "来歴・入手経路の説明なし",
    "no_source_url":                "出典URLなし",
    "weak_seller_info":             "販売者情報が弱い",
    "no_return":                    "返品不可",
    "few_transactions":             "取引履歴が少ない",
    "bad_reviews":                  "評価が低い・悪評",
    "multi_site_selling":           "同一商品が複数サイトで別名販売",
    "photo_reuse_suspected":        "商品写真の流用疑い",
    "below_market_price":           "相場より明らかに安い",
    "expensive_no_evidence":        "高額なのに根拠資料が少ない",
    "inflated_keywords":            "希少・宮廷・出土等で高額化",
    "vague_price_explanation":      "価格説明が抽象的",
    "few_photos":                   "写真が少ない",
    "front_only":                   "正面写真しかない",
    "no_side_bottom_closeup":       "側面・底面・拡大写真なし",
    "no_damage_explanation":        "傷・欠け・修理の説明なし",
    "no_transmitted_light":         "透過光写真なし",
    "no_uv_photo":                  "UV写真なし",
    "low_resolution":               "画像が低解像度",
    "color_correction_suspected":   "色補正・過度加工の疑い",
    "vague_description":            "販売説明が抽象語中心",
    "strong_selling_keywords":      "強い売り文句のみ",
    "vague_material":               "材質名が曖昧",
    "no_period_basis":              "年代根拠がない",
    "no_origin_basis":              "産地根拠がない",
    "no_size_weight":               "サイズ・重量の記載なし",
    "processing_suspected":         "人工処理疑い",
    "resin_suspected":              "樹脂含浸疑い",
    "dyeing_suspected":             "染色疑い",
    "acid_suspected":               "酸処理疑い",
    "wax_oil_suspected":            "蝋・油による艶出し疑い",
    "substitute_material_suspected":"代替材（ガラス・蛇紋石等）疑い",
    "too_uniform_color":            "色が均一すぎる",
    "unnatural_gloss":              "艶が不自然に強い",
    "unnatural_internal":           "内部構造が不自然",
    "antique_fake_suspected":       "仿古加工疑い",
    "artificial_soil_suspected":    "人工土沁疑い",
    "artificial_aging_suspected":   "人工風化疑い",
    "modern_tool_marks":            "工具痕が現代的",
    "unnatural_wear":               "孔・縁・角の摩耗が不自然",
    "ancient_no_provenance":        "古玉表記なのに来歴なし",
    "excavated_no_legality":        "出土品表記なのに合法性説明なし",
    "no_foot_photo":                "高台写真なし",
    "no_glaze_closeup":             "釉薬拡大写真なし",
    "no_repair_explanation":        "修理・ニュウ・金継ぎ説明なし",
    "no_mark_box_correspondence":   "銘・箱書き・共箱の対応不明",
    "no_kiln_basis":                "窯・作家・時代の根拠なし",
    "ceramic_expensive_no_evidence":"古陶磁で科学検査・来歴がなく高額",
    # 減点
    "has_reliable_certificate":     "信頼できる鑑別書あり",
    "major_auction_history":        "大手オークション履歴あり",
    "museum_publication":           "博物館・図録・専門書掲載あり",
    "has_return_guarantee":         "返品保証あり",
    "sufficient_hq_photos":         "高解像度写真が十分",
    "has_special_photos":           "透過光・UV・拡大写真あり",
    "seller_established":           "販売者が専門店で実績十分",
    "clear_provenance":             "来歴が明確",
}


def generate(item_id: int, db_path=None) -> Path:
    conn = get_connection(db_path) if db_path else get_connection()

    item = dict_from_row(conn.execute("SELECT * FROM items WHERE id=?", (item_id,)).fetchone())
    if not item:
        raise ValueError(f"Item {item_id} not found")

    assessment_row = conn.execute(
        "SELECT * FROM authenticity_assessments WHERE item_id=?", (item_id,)
    ).fetchone()
    assessment = dict_from_row(assessment_row) if assessment_row else {}
    if assessment:
        assessment["_item_price"] = item.get("price", 0)
        assessment = calculate(assessment)

    images = [dict_from_row(r) for r in conn.execute(
        "SELECT * FROM images WHERE item_id=? ORDER BY image_type", (item_id,)
    ).fetchall()]

    refs = [dict_from_row(r) for r in conn.execute(
        """SELECT r.* FROM references_ r
           JOIN item_references ir ON ir.reference_id = r.id
           WHERE ir.item_id=? ORDER BY r.year DESC""", (item_id,)
    ).fetchall()]

    fakes = [dict_from_row(r) for r in conn.execute(
        """SELECT ff.*, iff.match_confidence, iff.notes as match_notes
           FROM fake_features ff
           JOIN item_fake_features iff ON iff.fake_feature_id = ff.id
           WHERE iff.item_id=? ORDER BY ff.danger_level DESC""", (item_id,)
    ).fetchall()]

    auctions = [dict_from_row(r) for r in conn.execute(
        """SELECT a.*, ia.comparison_notes
           FROM auctions a
           JOIN item_auctions ia ON ia.auction_id = a.id
           WHERE ia.item_id=? ORDER BY a.sale_date DESC""", (item_id,)
    ).fetchall()]

    conn.close()

    score = assessment.get("calculated_score", 0)
    risk_level = assessment.get("risk_level", "未評価")
    purchase_advice = assessment.get("purchase_advice", "未評価")
    emoji = _RISK_EMOJI.get(risk_level, "⚪")
    today = datetime.date.today().isoformat()

    lines: list[str] = []
    a = lines.append

    a(f"# 真贋リスク評価レポート：{item['name']}")
    a(f"\n生成日：{today}　｜　Item ID：{item_id}")
    a("")

    # 結論
    a("---")
    a("## 結論")
    a("")
    a(f"**リスクスコア：{score}/100　{emoji} {risk_level}**")
    a("")
    a(f"**購入判断：{purchase_advice}**")
    a("")
    if assessment.get("force_high_risk"):
        a(f"> ⚠️ 強制高リスク判定：{assessment.get('force_reason', '')}")
        a("")
    if assessment.get("reasoning"):
        a(f"**判断理由：** {assessment['reasoning']}")
        a("")
    if assessment.get("authenticity_probability"):
        a(f"**真作可能性：** {assessment['authenticity_probability']}")
        a("")

    # 基本情報
    a("---")
    a("## 基本情報")
    a("")
    a("| 項目 | 内容 |")
    a("|------|------|")
    fields = [
        ("名称", "name"), ("分類", "category"), ("材質", "material"),
        ("推定年代", "estimated_period"), ("推定産地", "estimated_origin"),
        ("サイズ", "size_description"), ("重量", "weight_g"),
        ("価格", "price"), ("通貨", "currency"), ("販売元", "seller"),
        ("状態", "condition"), ("付属品", "accessories"),
        ("鑑別書", "has_certificate"), ("鑑別書機関", "certificate_issuer"),
        ("返品", "returnable"), ("取得日", "acquired_date"),
    ]
    for label, key in fields:
        val = item.get(key, "")
        if key == "has_certificate":
            val = "あり" if val else "なし"
        elif key == "returnable":
            val = "可" if val else "不可"
        elif key == "weight_g" and val:
            val = f"{val}g"
        if val not in (None, "", 0):
            a(f"| {label} | {val} |")
    a("")
    if item.get("source_url"):
        a(f"**出典URL：** {item['source_url']}")
        a("")
    if item.get("description"):
        a("**商品説明：**")
        a("")
        a(f"> {item['description']}")
        a("")

    # 画像一覧
    a("---")
    a("## 画像一覧")
    a("")
    if images:
        a("| 種別 | ファイル名 | パス | 出典 | メモ |")
        a("|------|-----------|------|------|------|")
        for img in images:
            a(f"| {img.get('image_type','')} | {img.get('filename','')} | `{img.get('file_path','')}` | {img.get('source_url','')} | {img.get('memo','')} |")
    else:
        a("*画像データなし*")
    a("")

    # 真贋リスク詳細
    a("---")
    a("## 真贋リスク評価")
    a("")
    if assessment:
        triggered_risks = assessment.get("_triggered_risks", [])
        triggered_reductions = assessment.get("_triggered_reductions", [])
        if triggered_risks:
            a("### リスク加点項目")
            a("")
            for flag in triggered_risks:
                pts = RISK_POINTS.get(flag, 0)
                label = _JP_LABELS.get(flag, flag)
                a(f"- **+{pts}点** {label}")
            a("")
        if triggered_reductions:
            a("### 減点項目")
            a("")
            for flag in triggered_reductions:
                pts = REDUCTION_POINTS.get(flag, 0)
                label = _JP_LABELS.get(flag, flag)
                a(f"- **{pts}点** {label}")
            a("")
        a(f"### 合計スコア：**{score}点 / 100点**　{emoji} {risk_level}")
        a("")
    else:
        a("*評価データなし*")
        a("")

    # 偽物特徴との一致
    a("---")
    a("## 偽物特徴との一致")
    a("")
    if fakes:
        for ff in fakes:
            danger = "🔴" * ff.get("danger_level", 0)
            conf = ff.get("match_confidence", "")
            a(f"### {ff['feature_name']}　危険度：{danger}")
            a("")
            a(f"- **対象分類：** {ff.get('target_category','')}")
            a(f"- **具体的特徴：** {ff.get('description','')}")
            a(f"- **観察方法：** {ff.get('observation_method','')}")
            a(f"- **判定根拠：** {ff.get('judgment_basis','')}")
            a(f"- **一致確信度：** {conf}")
            if ff.get("match_notes"):
                a(f"- **メモ：** {ff['match_notes']}")
            if ff.get("reference_url"):
                a(f"- **参考URL：** {ff['reference_url']}")
            a("")
    else:
        a("*偽物特徴との照合データなし*")
        a("")

    # オークション比較
    a("---")
    a("## 類似オークション比較")
    a("")
    if auctions:
        for auc in auctions:
            low = auc.get("estimate_low", "")
            high = auc.get("estimate_high", "")
            hammer = auc.get("hammer_price", "")
            cur = auc.get("currency", "JPY")
            estimate_str = f"{low:,}〜{high:,} {cur}" if low and high else "—"
            hammer_str = f"{hammer:,} {cur}" if hammer else "—"
            a(f"### {auc.get('auction_house','')}　ロット{auc.get('lot_number','')}")
            a("")
            a(f"| 項目 | 内容 |")
            a(f"|------|------|")
            a(f"| 作品名 | {auc.get('item_name','')} |")
            a(f"| 年代 | {auc.get('period','')} |")
            a(f"| 材質 | {auc.get('material','')} |")
            a(f"| サイズ | {auc.get('size_description','')} |")
            a(f"| 見積価格 | {estimate_str} |")
            a(f"| 落札価格 | {hammer_str} |")
            a(f"| 落札日 | {auc.get('sale_date','')} |")
            a(f"| 来歴 | {auc.get('provenance','')} |")
            a(f"| 状態 | {auc.get('condition_description','')} |")
            if auc.get("source_url"):
                a(f"| URL | {auc['source_url']} |")
            if auc.get("comparison_notes"):
                a(f"\n**比較メモ：** {auc['comparison_notes']}")
            a("")
    else:
        a("*オークション比較データなし*")
        a("")

    # 関連論文・資料
    a("---")
    a("## 関連論文・資料")
    a("")
    if refs:
        for ref in refs:
            reliability = "⭐" * ref.get("reliability", 0)
            a(f"### {ref['title']}　信頼度：{reliability}")
            a("")
            a(f"- **著者：** {ref.get('author','')}")
            a(f"- **年：** {ref.get('year','')}")
            a(f"- **種別：** {ref.get('ref_type','')}")
            if ref.get("url"):
                a(f"- **URL：** {ref['url']}")
            if ref.get("pdf_path"):
                a(f"- **PDF：** `{ref['pdf_path']}`")
            if ref.get("summary"):
                a(f"- **要約：** {ref['summary']}")
            if ref.get("key_points"):
                a(f"- **重要ポイント：** {ref['key_points']}")
            if ref.get("related_fake_features"):
                a(f"- **関連偽物特徴：** {ref['related_fake_features']}")
            a("")
    else:
        a("*関連資料なし*")
        a("")

    # 購入判断
    a("---")
    a("## 購入判断")
    a("")
    a(f"| リスクスコア | リスクレベル | 判断 |")
    a(f"|-------------|------------|------|")
    a(f"| **{score}/100** | **{emoji} {risk_level}** | **{purchase_advice}** |")
    a("")
    if assessment.get("force_high_risk"):
        a(f"> ⚠️ **強制高リスク判定が適用されています：** {assessment.get('force_reason','')}")
        a("")

    # 追加確認事項
    a("---")
    a("## 追加確認事項")
    a("")
    checks: list[str] = []
    if not item.get("has_certificate"):
        checks.append("第三者機関による鑑別書の取得")
    if assessment.get("no_transmitted_light"):
        checks.append("透過光写真の要求（内部構造・インクルージョン確認）")
    if assessment.get("no_uv_photo"):
        checks.append("UV（紫外線）写真の要求（処理有無の確認）")
    if assessment.get("photo_reuse_suspected"):
        checks.append("画像の逆引き検索による流用確認（Google画像検索等）")
    if assessment.get("no_provenance"):
        checks.append("来歴・旧蔵・入手経路の文書による証明")
    if not item.get("returnable"):
        checks.append("返品条件の交渉または回避")
    if assessment.get("below_market_price"):
        checks.append("類似品のオークション・市場価格との比較確認")
    if not checks:
        checks.append("現時点で特記事項なし")
    for c in checks:
        a(f"- [ ] {c}")
    a("")
    a("---")
    a(f"*本レポートは購入判断支援用のリスク評価です。断定的な真贋鑑定ではありません。*")
    a(f"*生成日時：{datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}*")

    safe_name = "".join(c if c.isalnum() or c in "-_" else "_" for c in item["name"])
    filename = REPORTS_DIR / f"report_{item_id}_{safe_name}_{today}.md"
    filename.write_text("\n".join(lines), encoding="utf-8")
    return filename
