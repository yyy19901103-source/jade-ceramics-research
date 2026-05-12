"""
4-agent purchase decision system for jade/antique items.

BuyAgent      — argues FOR purchasing
NoBuyAgent    — argues AGAINST purchasing
JudgeAgent    — makes final verdict from both sides
ReflectionAgent — post-purchase review of decision quality
"""
from __future__ import annotations
import json
from dataclasses import dataclass, field, asdict

# ---------------------------------------------------------------------------
# Evidence strength scale
# ---------------------------------------------------------------------------
# 5: Museum / academic paper / certification body / major auction result
# 4: Established specialist shop / catalogue / reference book
# 3: General auction result / multiple market comparisons
# 2: Seller description / personal blog / SNS
# 1: Unknown source / sales text only

EVIDENCE = {
    "museum_publication":       5,
    "major_auction_history":    5,
    "has_reliable_certificate": 5,
    "seller_established":       4,
    "clear_provenance":         4,
    "has_return_guarantee":     3,
    "sufficient_hq_photos":     3,
    "has_special_photos":       3,
    "auction_comparison":       3,
    "ref_paper":                5,
    "ref_museum":               5,
    "ref_certification":        4,
    "ref_auction":              3,
    "ref_market":               2,
    "seller_description":       2,
    "no_evidence":              1,
}

VERDICT_LABELS = {
    "buy":            "購入候補",
    "watch":          "様子見",
    "need_more_info": "追加情報が必要",
    "no_buy":         "購入しない",
    "no_buy_strong":  "購入非推奨",
}

OUTCOME_LABELS = {
    "genuine":         "本物だった",
    "fake":            "偽物だった",
    "treated":         "処理品だった",
    "overpriced":      "高すぎた",
    "good_purchase":   "良い買い物だった",
    "bad_purchase":    "悪い買い物だった",
    "no_buy_correct":  "買わなくて正解だった",
    "unknown":         "判断不能",
}

# High-risk categories that trigger conservative judgment
CONSERVATIVE_CATEGORIES = {"古玉", "翡翠", "白玉", "和田白玉"}
CONSERVATIVE_KEYWORDS = {"羊脂", "出土", "漢代", "戦国", "周代", "商代", "良渚"}


@dataclass
class Reason:
    text: str
    evidence_source: str    # what backs this up
    evidence_strength: int  # 1-5
    fact_type: str          # fact / inference / hypothesis


@dataclass
class BuyResult:
    conclusion: str = ""
    reasons: list[Reason] = field(default_factory=list)
    conditions: list[str] = field(default_factory=list)
    weak_points: list[str] = field(default_factory=list)
    overall_strength: float = 0.0


@dataclass
class NoBuyResult:
    conclusion: str = ""
    reasons: list[Reason] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    info_gaps: list[str] = field(default_factory=list)
    overall_strength: float = 0.0


@dataclass
class JudgeResult:
    verdict: str = "need_more_info"    # buy / watch / need_more_info / no_buy / no_buy_strong
    action: str = ""
    buy_valid: list[str] = field(default_factory=list)
    nobuy_valid: list[str] = field(default_factory=list)
    evidence_score: float = 0.0
    info_shortage_rate: float = 0.0
    additional_checks: list[str] = field(default_factory=list)
    comment: str = ""
    forced_conservative: bool = False


@dataclass
class ReflectionResult:
    has_error: bool = False
    weak_agents: list[str] = field(default_factory=list)
    missed_evidence: list[str] = field(default_factory=list)
    weight_problems: list[str] = field(default_factory=list)
    next_checks: list[str] = field(default_factory=list)
    rule_improvements: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# BuyAgent
# ---------------------------------------------------------------------------
class BuyAgent:
    """Argues FOR buying. Looks for value, quality, and positive evidence."""

    def analyze(
        self,
        item: dict,
        assessment: dict,
        images: list[dict],
        refs: list[dict],
        fakes: list[dict],
        auctions: list[dict],
    ) -> BuyResult:
        result = BuyResult()
        reasons: list[Reason] = []

        # 1. Reliable certificate
        if item.get("has_certificate") and item.get("certificate_issuer"):
            issuer = item["certificate_issuer"]
            strength = 5 if any(k in issuer for k in ("GIA", "中央", "AGT", "GRS")) else 4
            reasons.append(Reason(
                text=f"信頼できる鑑別書あり（{issuer}）",
                evidence_source=f"鑑別書：{issuer}",
                evidence_strength=strength,
                fact_type="fact",
            ))

        # 2. Established seller + return policy
        if assessment.get("seller_established"):
            reasons.append(Reason(
                text="販売者が専門店で実績十分",
                evidence_source="販売者情報",
                evidence_strength=4,
                fact_type="fact",
            ))
        if item.get("returnable"):
            reasons.append(Reason(
                text="返品可能（リスク軽減）",
                evidence_source="販売条件",
                evidence_strength=3,
                fact_type="fact",
            ))

        # 3. Major auction or museum record
        if assessment.get("major_auction_history"):
            reasons.append(Reason(
                text="大手オークション落札実績あり",
                evidence_source="オークション記録",
                evidence_strength=5,
                fact_type="fact",
            ))
        if assessment.get("museum_publication"):
            reasons.append(Reason(
                text="博物館・図録・専門書掲載あり",
                evidence_source="出版物・博物館資料",
                evidence_strength=5,
                fact_type="fact",
            ))

        # 4. Photo quality
        if assessment.get("sufficient_hq_photos") or assessment.get("has_special_photos"):
            photo_types = [img.get("image_type", "") for img in images]
            special = [t for t in photo_types if t in ("透過光", "UV", "拡大", "底", "工具痕")]
            if special:
                reasons.append(Reason(
                    text=f"高品質写真あり（{', '.join(special)}）",
                    evidence_source="商品写真",
                    evidence_strength=3,
                    fact_type="fact",
                ))

        # 5. Clear provenance
        if assessment.get("clear_provenance"):
            reasons.append(Reason(
                text="来歴が明確に記載されている",
                evidence_source="販売説明・添付資料",
                evidence_strength=4,
                fact_type="fact",
            ))

        # 6. Reference papers support authenticity
        strong_refs = [r for r in refs if r.get("reliability", 0) >= 4]
        if strong_refs:
            r0 = strong_refs[0]
            reasons.append(Reason(
                text=f"関連学術資料あり（{r0['title'][:30]}…）",
                evidence_source=r0.get("url", ""),
                evidence_strength=min(5, r0.get("reliability", 3)),
                fact_type="inference",
            ))

        # 7. Price vs auction (below market = potential value)
        if auctions and item.get("price"):
            hammer_prices = [a["hammer_price"] for a in auctions if a.get("hammer_price")]
            if hammer_prices:
                avg = sum(hammer_prices) / len(hammer_prices)
                if item["price"] < avg * 0.8:
                    reasons.append(Reason(
                        text=f"類似オークション落札均価（{avg:,.0f}）より安い可能性",
                        evidence_source="オークション比較",
                        evidence_strength=3,
                        fact_type="inference",
                    ))

        # 8. Low calculated risk score
        score = assessment.get("calculated_score", 100)
        if score <= 20:
            reasons.append(Reason(
                text=f"リスクスコアが低い（{score}/100 低リスク）",
                evidence_source="リスクスコア計算",
                evidence_strength=3,
                fact_type="fact",
            ))

        # Limit to max 5
        reasons = sorted(reasons, key=lambda r: r.evidence_strength, reverse=True)[:5]
        result.reasons = reasons

        # Conditions
        if not item.get("has_certificate"):
            result.conditions.append("購入前に第三者機関の鑑別書を取得すること")
        if not item.get("returnable"):
            result.conditions.append("返品交渉を試みること")
        if not assessment.get("sufficient_hq_photos"):
            result.conditions.append("透過光・UV・拡大写真を追加請求すること")

        # Weak points
        if not reasons:
            result.weak_points.append("買う根拠が見当たらない")
        if not item.get("has_certificate"):
            result.weak_points.append("鑑別書なしのため材質の客観的証明がない")
        if assessment.get("no_provenance"):
            result.weak_points.append("来歴不明のため真作証明が困難")

        if reasons:
            result.overall_strength = sum(r.evidence_strength for r in reasons) / len(reasons)
            result.conclusion = f"買う根拠あり（平均根拠強度 {result.overall_strength:.1f}/5）"
        else:
            result.overall_strength = 0.0
            result.conclusion = "買う積極的根拠が見当たらない"

        return result


# ---------------------------------------------------------------------------
# NoBuyAgent
# ---------------------------------------------------------------------------
class NoBuyAgent:
    """Argues AGAINST buying. Conservative for jade/antiques."""

    def analyze(
        self,
        item: dict,
        assessment: dict,
        images: list[dict],
        refs: list[dict],
        fakes: list[dict],
        auctions: list[dict],
    ) -> NoBuyResult:
        result = NoBuyResult()
        reasons: list[Reason] = []

        # Is this a conservative category?
        cat = item.get("category", "")
        desc = item.get("description", "") or ""
        name = item.get("name", "") or ""
        is_conservative = (
            cat in CONSERVATIVE_CATEGORIES
            or any(kw in desc or kw in name for kw in CONSERVATIVE_KEYWORDS)
        )

        # 1. Force-high-risk flags
        if assessment.get("photo_reuse_suspected"):
            reasons.append(Reason(
                text="商品写真の流用が疑われる（強制高リスク）",
                evidence_source="写真逆引き検索未実施 or 疑い",
                evidence_strength=5,
                fact_type="inference",
            ))
        if assessment.get("cert_item_mismatch"):
            reasons.append(Reason(
                text="鑑別書と商品の対応が確認できない（強制高リスク）",
                evidence_source="鑑別書・写真照合",
                evidence_strength=5,
                fact_type="fact",
            ))

        # 2. Artificial processing flags
        process_flags = {
            "processing_suspected": "人工処理疑い",
            "resin_suspected": "樹脂含浸（B貨）疑い",
            "dyeing_suspected": "染色（C貨）疑い",
            "acid_suspected": "酸処理疑い",
        }
        for flag, label in process_flags.items():
            if assessment.get(flag):
                reasons.append(Reason(
                    text=label,
                    evidence_source="外観観察・リスク評価",
                    evidence_strength=4,
                    fact_type="inference",
                ))

        # 3. Fake feature matches
        high_danger_fakes = [f for f in fakes if f.get("danger_level", 0) >= 4]
        if high_danger_fakes:
            ff = high_danger_fakes[0]
            conf = ff.get("match_confidence", "不明")
            reasons.append(Reason(
                text=f"高危険度偽物特徴と一致：{ff['feature_name']}（一致確信度：{conf}）",
                evidence_source=ff.get("reference_url", "偽物特徴DB"),
                evidence_strength=4,
                fact_type="inference",
            ))

        # 4. Missing certificate for high-value item
        price = item.get("price", 0) or 0
        if not item.get("has_certificate") and price > 100000:
            reasons.append(Reason(
                text=f"高額品（{price:,.0f}円）なのに鑑別書なし",
                evidence_source="販売情報",
                evidence_strength=4,
                fact_type="fact",
            ))

        # 5. No provenance + conservative category
        if assessment.get("no_provenance") or assessment.get("ancient_no_provenance"):
            strength = 5 if is_conservative else 3
            reasons.append(Reason(
                text="来歴・入手経路の説明なし",
                evidence_source="販売説明",
                evidence_strength=strength,
                fact_type="fact",
            ))

        # 6. Photo shortage
        photo_issues = []
        if assessment.get("few_photos") or assessment.get("front_only"):
            photo_issues.append("写真が少ない・正面のみ")
        if assessment.get("no_transmitted_light") and cat in ("翡翠", "白玉", "和田白玉", "古玉"):
            photo_issues.append("透過光写真なし（玉器で必須）")
        if assessment.get("no_uv_photo") and cat == "翡翠":
            photo_issues.append("UV写真なし（翡翠で必須）")
        if photo_issues:
            reasons.append(Reason(
                text="写真不足：" + " / ".join(photo_issues),
                evidence_source="商品写真確認",
                evidence_strength=3,
                fact_type="fact",
            ))

        # 7. Price anomaly vs auctions
        if assessment.get("below_market_price") and auctions:
            reasons.append(Reason(
                text="相場より明らかに安い（偽物・処理品の可能性）",
                evidence_source="オークション相場比較",
                evidence_strength=3,
                fact_type="inference",
            ))

        # 8. Excavated item + no legality
        if assessment.get("excavated_no_legality"):
            reasons.append(Reason(
                text="出土品表記なのに合法性・来歴の説明なし（強制高リスク）",
                evidence_source="販売説明",
                evidence_strength=5,
                fact_type="fact",
            ))

        # Conservative boost: add generic conservative reason
        if is_conservative and len(reasons) < 3:
            reasons.append(Reason(
                text=f"分類・キーワードが保守的判断対象（{cat} / {name[:20]}）",
                evidence_source="カテゴリルール",
                evidence_strength=3,
                fact_type="fact",
            ))

        reasons = sorted(reasons, key=lambda r: r.evidence_strength, reverse=True)[:5]
        result.reasons = reasons

        # Info gaps
        if assessment.get("few_photos") or assessment.get("front_only"):
            result.info_gaps.append("透過光・UV・側面・底面写真")
        if not item.get("has_certificate"):
            result.info_gaps.append("第三者機関の鑑別書")
        if assessment.get("no_provenance"):
            result.info_gaps.append("来歴・旧蔵証明")
        if not item.get("returnable"):
            result.info_gaps.append("返品条件の確認")
        if not item.get("source_url"):
            result.info_gaps.append("出典URL")

        # Risks summary
        score = assessment.get("calculated_score", 50)
        result.risks.append(f"リスクスコア {score}/100")
        if assessment.get("force_high_risk"):
            result.risks.append(f"強制高リスク判定：{assessment.get('force_reason', '')}")

        if reasons:
            result.overall_strength = sum(r.evidence_strength for r in reasons) / len(reasons)
            result.conclusion = f"買わない根拠あり（平均根拠強度 {result.overall_strength:.1f}/5）"
        else:
            result.overall_strength = 1.0
            result.conclusion = "買わない積極的根拠は少ないが情報不足"

        return result


# ---------------------------------------------------------------------------
# JudgeAgent
# ---------------------------------------------------------------------------
class JudgeAgent:
    """Makes the final verdict. Evidence strength > number of reasons."""

    # Info shortage factors
    _INFO_ITEMS = [
        ("has_certificate",         0.20),
        ("no_transmitted_light",    0.10),
        ("no_uv_photo",             0.10),
        ("no_side_bottom_closeup",  0.10),
        ("no_provenance",           0.15),
        ("returnable",              0.05),
        ("source_url",              0.05),
        ("weak_seller_info",        0.10),
        ("few_photos",              0.10),
        ("no_size_weight",          0.05),
    ]

    def decide(
        self,
        buy: BuyResult,
        nobuy: NoBuyResult,
        item: dict,
        assessment: dict,
        auctions: list[dict],
    ) -> JudgeResult:
        result = JudgeResult()

        # Evidence scores
        buy_score = buy.overall_strength
        nobuy_score = nobuy.overall_strength

        # Score gap
        result.evidence_score = round((buy_score + nobuy_score) / 2, 2)

        # Information shortage rate
        shortage = 0.0
        for key, weight in self._INFO_ITEMS:
            if key in ("has_certificate", "returnable", "source_url"):
                # These are item fields (1=good, 0=gap)
                if not item.get(key):
                    shortage += weight
            else:
                # These are assessment flags (1=problem)
                if assessment.get(key):
                    shortage += weight
        result.info_shortage_rate = min(1.0, shortage)

        # Conservative trigger
        cat = item.get("category", "")
        name = item.get("name", "") or ""
        desc = item.get("description", "") or ""
        is_conservative = (
            cat in CONSERVATIVE_CATEGORIES
            or any(kw in desc or kw in name for kw in CONSERVATIVE_KEYWORDS)
        )
        result.forced_conservative = is_conservative

        # Absolute blockers → no_buy_strong
        force_blockers = [
            "photo_reuse_suspected",
            "cert_item_mismatch",
            "excavated_no_legality",
        ]
        if any(assessment.get(f) for f in force_blockers):
            result.verdict = "no_buy_strong"
            result.comment = "強制高リスク要因が存在します。購入は非推奨です。"
            result.action = "購入しない"
            _fill_valid(result, buy, nobuy)
            _fill_checks(result, item, assessment)
            return result

        # High info shortage with no buy strengths → need_more_info
        if result.info_shortage_rate >= 0.40 and buy_score < 3.0:
            result.verdict = "need_more_info"
            result.comment = (
                f"情報不足率 {result.info_shortage_rate:.0%}。"
                "追加情報なしでの判断は困難です。"
            )
            result.action = "追加写真・鑑別書を入手してから再判断"
            _fill_valid(result, buy, nobuy)
            _fill_checks(result, item, assessment)
            return result

        # Strong no-buy evidence dominates
        processing_flags = sum(
            1 for f in ("processing_suspected", "resin_suspected", "dyeing_suspected", "acid_suspected")
            if assessment.get(f)
        )
        if nobuy_score >= 4.0 or processing_flags >= 2:
            result.verdict = "no_buy_strong" if nobuy_score >= 4.5 else "no_buy"
            result.comment = "No-Buy Agentの根拠が強く、購入リスクが高いと判断します。"
            result.action = "購入しない"
            _fill_valid(result, buy, nobuy)
            _fill_checks(result, item, assessment)
            return result

        # Conservative category with weak buy evidence
        if is_conservative and buy_score < 3.5:
            result.verdict = "watch"
            result.comment = (
                f"「{cat}」は保守的判断対象です。"
                f"Buy根拠強度（{buy_score:.1f}）が基準（3.5）未満のため様子見を推奨します。"
            )
            result.action = "様子見・追加確認後に再検討"
            _fill_valid(result, buy, nobuy)
            _fill_checks(result, item, assessment)
            return result

        # Buy wins clearly
        if buy_score >= 4.0 and nobuy_score < 3.0:
            result.verdict = "buy"
            result.comment = "Buy Agentの根拠が強く、No-Buy根拠が弱い。購入候補と判断します。"
            result.action = "購入候補（条件付き）"
        elif buy_score >= 3.0 and nobuy_score < 3.5:
            result.verdict = "watch"
            result.comment = "Buy・No-Buy双方に根拠があります。追加確認後に判断してください。"
            result.action = "追加確認後に検討"
        else:
            result.verdict = "no_buy"
            result.comment = "No-Buy根拠がBuy根拠を上回るため、購入しないことを推奨します。"
            result.action = "購入しない"

        _fill_valid(result, buy, nobuy)
        _fill_checks(result, item, assessment)
        return result


def _fill_valid(result: JudgeResult, buy: BuyResult, nobuy: NoBuyResult):
    result.buy_valid = [r.text for r in buy.reasons if r.evidence_strength >= 3]
    result.nobuy_valid = [r.text for r in nobuy.reasons if r.evidence_strength >= 3]


def _fill_checks(result: JudgeResult, item: dict, assessment: dict):
    checks = []
    if not item.get("has_certificate"):
        checks.append("第三者機関の鑑別書を取得する")
    if assessment.get("no_transmitted_light"):
        checks.append("透過光写真を要求する（内部構造・インクルージョン確認）")
    if assessment.get("no_uv_photo"):
        checks.append("UV（紫外線）写真を要求する（処理品判定）")
    if assessment.get("photo_reuse_suspected") or assessment.get("few_photos"):
        checks.append("Google画像逆引き検索で写真流用を確認する")
    if assessment.get("no_provenance"):
        checks.append("来歴・旧蔵・入手経路の文書証明を求める")
    if not item.get("returnable"):
        checks.append("返品条件の交渉を試みる")
    if assessment.get("below_market_price"):
        checks.append("類似品のオークション実績と価格を再確認する")
    result.additional_checks = checks


# ---------------------------------------------------------------------------
# ReflectionAgent
# ---------------------------------------------------------------------------
class ReflectionAgent:
    """Reviews the judgment quality after the actual outcome is known."""

    ACTUAL_OUTCOMES = set(OUTCOME_LABELS.keys())

    def reflect(
        self,
        buy: BuyResult,
        nobuy: NoBuyResult,
        judge: JudgeResult,
        actual_outcome: str,
    ) -> ReflectionResult:
        result = ReflectionResult()
        outcome = actual_outcome.lower()

        if outcome not in self.ACTUAL_OUTCOMES:
            result.missed_evidence.append(f"不明な実際結果コード：{actual_outcome}")
            return result

        # Was the judgment correct?
        verdict = judge.verdict
        good_outcomes = {"genuine", "good_purchase"}
        bad_outcomes = {"fake", "treated", "overpriced", "bad_purchase"}

        if verdict in ("buy",) and outcome in bad_outcomes:
            result.has_error = True
            result.weak_agents.append("BuyAgent（過剰に楽観的だった）")
            result.weak_agents.append("JudgeAgent（No-Buy根拠の重み付けが不足）")

        elif verdict in ("no_buy", "no_buy_strong") and outcome in good_outcomes:
            result.has_error = True
            result.weak_agents.append("NoBuyAgent（過剰に保守的だった）")
            result.weak_agents.append("JudgeAgent（Buy根拠の重み付けが不足）")

        elif verdict in ("watch", "need_more_info") and outcome in bad_outcomes:
            result.has_error = True
            result.weak_agents.append("JudgeAgent（様子見判定だったが偽物・処理品だった）")

        elif verdict == "no_buy_correct" or (
            verdict in ("no_buy", "no_buy_strong") and outcome == "no_buy_correct"
        ):
            result.has_error = False

        # Missed evidence analysis
        if outcome == "fake" and not any("偽物" in r.text for r in nobuy.reasons):
            result.missed_evidence.append("NoBuyAgentが偽物特徴を明示的に指摘していなかった")
        if outcome == "treated" and not any("処理" in r.text for r in nobuy.reasons):
            result.missed_evidence.append("NoBuyAgentが人工処理リスクを明示していなかった")
        if outcome == "overpriced" and not any("相場" in r.text for r in nobuy.reasons):
            result.missed_evidence.append("NoBuyAgentが価格乖離を指摘していなかった")
        if outcome in bad_outcomes and judge.info_shortage_rate < 0.3:
            result.missed_evidence.append(
                f"情報不足率({judge.info_shortage_rate:.0%})が低く見積もられていた可能性"
            )

        # Weight problems
        if result.has_error:
            if outcome in bad_outcomes and len(nobuy.reasons) > len(buy.reasons):
                result.weight_problems.append(
                    "No-Buy理由の数はBuyより多かったが判断に反映されなかった"
                )
            if outcome in good_outcomes and judge.forced_conservative:
                result.weight_problems.append(
                    "保守的カテゴリとして扱ったが実際には問題なかった"
                )

        # Next checks
        if outcome in ("fake", "treated"):
            result.next_checks.append("購入前にUV写真・透過光写真を必ず要求する")
            result.next_checks.append("鑑別書は写真と対応を確認する")
            result.next_checks.append("Google画像逆引き検索を必ず実施する")
        if outcome == "overpriced":
            result.next_checks.append("複数オークションの落札価格と比較する")
            result.next_checks.append("販売価格の根拠資料を必ず要求する")

        # Rule improvement proposals (not applied automatically)
        if outcome == "fake" and not any("流用" in r.text for r in nobuy.reasons):
            result.rule_improvements.append(
                "[提案] 写真流用チェックをNoBuyAgentの必須チェック項目に追加する"
            )
        if outcome == "treated":
            result.rule_improvements.append(
                "[提案] 翡翠・白玉カテゴリではUV写真なしを強制高リスクに格上げする"
            )

        return result


# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
def reason_to_dict(r: Reason) -> dict:
    return asdict(r)


def buy_result_to_dict(b: BuyResult) -> dict:
    d = asdict(b)
    d["reasons"] = [asdict(r) for r in b.reasons]
    return d


def nobuy_result_to_dict(n: NoBuyResult) -> dict:
    d = asdict(n)
    d["reasons"] = [asdict(r) for r in n.reasons]
    return d


def judge_result_to_dict(j: JudgeResult) -> dict:
    return asdict(j)


def reflection_result_to_dict(r: ReflectionResult) -> dict:
    return asdict(r)
