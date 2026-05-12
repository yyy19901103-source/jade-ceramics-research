"""Risk score calculation engine based on the jade/antique assessment specification."""

RISK_POINTS: dict[str, int] = {
    # 証明・来歴リスク
    "no_certificate":           15,
    "expensive_no_cert":        20,
    "unknown_cert_issuer":      20,
    "unclear_cert_image":       15,
    "cert_item_mismatch":       25,
    "no_provenance":            15,
    "no_source_url":            20,
    # 販売者リスク
    "weak_seller_info":         15,
    "no_return":                10,
    "few_transactions":         10,
    "bad_reviews":              20,
    "multi_site_selling":       25,
    "photo_reuse_suspected":    30,
    # 価格リスク
    "below_market_price":       20,
    "expensive_no_evidence":    20,
    "inflated_keywords":        15,
    "vague_price_explanation":  10,
    # 写真・観察不足リスク
    "few_photos":               15,
    "front_only":               15,
    "no_side_bottom_closeup":   15,
    "no_damage_explanation":    10,
    "no_transmitted_light":     10,
    "no_uv_photo":              10,
    "low_resolution":           10,
    "color_correction_suspected": 15,
    # 表現・説明リスク
    "vague_description":        10,
    "strong_selling_keywords":  15,
    "vague_material":           10,
    "no_period_basis":          15,
    "no_origin_basis":          10,
    "no_size_weight":           10,
    # 材質・人工処理リスク
    "processing_suspected":             30,
    "resin_suspected":                  30,
    "dyeing_suspected":                 25,
    "acid_suspected":                   25,
    "wax_oil_suspected":                15,
    "substitute_material_suspected":    30,
    "too_uniform_color":                10,
    "unnatural_gloss":                  10,
    "unnatural_internal":               15,
    # 古玉・仿古リスク
    "antique_fake_suspected":       30,
    "artificial_soil_suspected":    25,
    "artificial_aging_suspected":   25,
    "modern_tool_marks":            20,
    "unnatural_wear":               20,
    "ancient_no_provenance":        25,
    "excavated_no_legality":        30,
    # 古陶磁・陶芸リスク
    "no_foot_photo":                15,
    "no_glaze_closeup":             10,
    "no_repair_explanation":        15,
    "no_mark_box_correspondence":   15,
    "no_kiln_basis":                15,
    "ceramic_expensive_no_evidence": 20,
}

REDUCTION_POINTS: dict[str, int] = {
    "has_reliable_certificate": -20,
    "major_auction_history":    -25,
    "museum_publication":       -25,
    "has_return_guarantee":     -10,
    "sufficient_hq_photos":     -10,
    "has_special_photos":       -10,
    "seller_established":       -15,
    "clear_provenance":         -15,
}

# これらが True なら強制的に高リスク（61点以上）
FORCE_HIGH_RISK_FLAGS = {
    "photo_reuse_suspected",
    "cert_item_mismatch",
    "processing_suspected",
    "resin_suspected",
    "dyeing_suspected",
    "acid_suspected",
    "ancient_no_provenance",
    "excavated_no_legality",
}

RISK_LEVELS = [
    (20, "低リスク",       "購入候補"),
    (40, "注意",           "追加確認後に検討"),
    (60, "要警戒",         "原則慎重"),
    (80, "高リスク",       "基本購入しない"),
    (100, "購入非推奨",    "購入非推奨"),
]

FORCE_HIGH_RISK_MINIMUM = 61


def calculate(assessment: dict) -> dict:
    """Return updated assessment dict with calculated_score, risk_level, force_high_risk."""
    raw = 0
    triggered_risks: list[str] = []
    triggered_reductions: list[str] = []
    force_flags: list[str] = []

    for flag, points in RISK_POINTS.items():
        if assessment.get(flag):
            raw += points
            triggered_risks.append(flag)
            if flag in FORCE_HIGH_RISK_FLAGS:
                force_flags.append(flag)

    for flag, points in REDUCTION_POINTS.items():
        if assessment.get(flag):
            raw += points  # points is negative
            triggered_reductions.append(flag)

    # 高額品かつ返品不可かつ鑑別書なし の複合チェック
    item_price = assessment.get("_item_price", 0) or 0
    if (item_price > 50000
            and assessment.get("no_return")
            and assessment.get("no_certificate")):
        force_flags.append("expensive_no_return_no_cert")

    score = max(0, min(100, raw))
    force_high = bool(force_flags)

    if force_high and score < FORCE_HIGH_RISK_MINIMUM:
        score = FORCE_HIGH_RISK_MINIMUM

    risk_level = "購入非推奨"
    purchase_advice = "購入非推奨"
    for threshold, level, advice in RISK_LEVELS:
        if score <= threshold:
            risk_level = level
            purchase_advice = advice
            break

    return {
        **assessment,
        "calculated_score": score,
        "risk_level": risk_level,
        "purchase_advice": purchase_advice,
        "force_high_risk": 1 if force_high else 0,
        "force_reason": ", ".join(force_flags) if force_flags else "",
        "_triggered_risks": triggered_risks,
        "_triggered_reductions": triggered_reductions,
    }


def score_label(score: int) -> str:
    for threshold, level, _ in RISK_LEVELS:
        if score <= threshold:
            return level
    return "購入非推奨"
