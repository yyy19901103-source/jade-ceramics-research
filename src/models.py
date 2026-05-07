"""SQLite schema definitions."""

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

-- 作品・商品データ
CREATE TABLE IF NOT EXISTS items (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    name                TEXT NOT NULL,
    category            TEXT,          -- 翡翠/白玉/和田白玉/古玉/古陶磁/陶芸アンティーク/芸術品
    material            TEXT,
    estimated_period    TEXT,
    estimated_origin    TEXT,
    size_description    TEXT,
    weight_g            REAL,
    price               REAL,
    currency            TEXT DEFAULT 'JPY',
    seller              TEXT,
    source_url          TEXT,
    acquired_date       TEXT,
    description         TEXT,
    condition           TEXT,
    accessories         TEXT,
    has_certificate     INTEGER DEFAULT 0,  -- 0=なし 1=あり
    certificate_issuer  TEXT,
    returnable          INTEGER DEFAULT 0,  -- 0=不可 1=可
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 画像データ
CREATE TABLE IF NOT EXISTS images (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER REFERENCES items(id) ON DELETE CASCADE,
    filename    TEXT NOT NULL,
    file_path   TEXT NOT NULL,
    image_type  TEXT,   -- 正面/背面/側面/底/透過光/UV/拡大/傷/工具痕
    source_url  TEXT,
    rights_info TEXT,
    memo        TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 真贋・リスク評価
CREATE TABLE IF NOT EXISTS authenticity_assessments (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    item_id     INTEGER UNIQUE REFERENCES items(id) ON DELETE CASCADE,

    -- 証明・来歴リスク
    no_certificate          INTEGER DEFAULT 0,
    expensive_no_cert       INTEGER DEFAULT 0,
    unknown_cert_issuer     INTEGER DEFAULT 0,
    unclear_cert_image      INTEGER DEFAULT 0,
    cert_item_mismatch      INTEGER DEFAULT 0,
    no_provenance           INTEGER DEFAULT 0,
    no_source_url           INTEGER DEFAULT 0,

    -- 販売者リスク
    weak_seller_info        INTEGER DEFAULT 0,
    no_return               INTEGER DEFAULT 0,
    few_transactions        INTEGER DEFAULT 0,
    bad_reviews             INTEGER DEFAULT 0,
    multi_site_selling      INTEGER DEFAULT 0,
    photo_reuse_suspected   INTEGER DEFAULT 0,

    -- 価格リスク
    below_market_price      INTEGER DEFAULT 0,
    expensive_no_evidence   INTEGER DEFAULT 0,
    inflated_keywords       INTEGER DEFAULT 0,
    vague_price_explanation INTEGER DEFAULT 0,

    -- 写真・観察不足リスク
    few_photos              INTEGER DEFAULT 0,
    front_only              INTEGER DEFAULT 0,
    no_side_bottom_closeup  INTEGER DEFAULT 0,
    no_damage_explanation   INTEGER DEFAULT 0,
    no_transmitted_light    INTEGER DEFAULT 0,
    no_uv_photo             INTEGER DEFAULT 0,
    low_resolution          INTEGER DEFAULT 0,
    color_correction_suspected INTEGER DEFAULT 0,

    -- 表現・説明リスク
    vague_description       INTEGER DEFAULT 0,
    strong_selling_keywords INTEGER DEFAULT 0,
    vague_material          INTEGER DEFAULT 0,
    no_period_basis         INTEGER DEFAULT 0,
    no_origin_basis         INTEGER DEFAULT 0,
    no_size_weight          INTEGER DEFAULT 0,

    -- 材質・人工処理リスク
    processing_suspected        INTEGER DEFAULT 0,
    resin_suspected             INTEGER DEFAULT 0,
    dyeing_suspected            INTEGER DEFAULT 0,
    acid_suspected              INTEGER DEFAULT 0,
    wax_oil_suspected           INTEGER DEFAULT 0,
    substitute_material_suspected INTEGER DEFAULT 0,
    too_uniform_color           INTEGER DEFAULT 0,
    unnatural_gloss             INTEGER DEFAULT 0,
    unnatural_internal          INTEGER DEFAULT 0,

    -- 古玉・仿古リスク
    antique_fake_suspected      INTEGER DEFAULT 0,
    artificial_soil_suspected   INTEGER DEFAULT 0,
    artificial_aging_suspected  INTEGER DEFAULT 0,
    modern_tool_marks           INTEGER DEFAULT 0,
    unnatural_wear              INTEGER DEFAULT 0,
    ancient_no_provenance       INTEGER DEFAULT 0,
    excavated_no_legality       INTEGER DEFAULT 0,

    -- 古陶磁・陶芸リスク
    no_foot_photo               INTEGER DEFAULT 0,
    no_glaze_closeup            INTEGER DEFAULT 0,
    no_repair_explanation       INTEGER DEFAULT 0,
    no_mark_box_correspondence  INTEGER DEFAULT 0,
    no_kiln_basis               INTEGER DEFAULT 0,
    ceramic_expensive_no_evidence INTEGER DEFAULT 0,

    -- 減点項目
    has_reliable_certificate    INTEGER DEFAULT 0,
    major_auction_history       INTEGER DEFAULT 0,
    museum_publication          INTEGER DEFAULT 0,
    has_return_guarantee        INTEGER DEFAULT 0,
    sufficient_hq_photos        INTEGER DEFAULT 0,
    has_special_photos          INTEGER DEFAULT 0,
    seller_established          INTEGER DEFAULT 0,
    clear_provenance            INTEGER DEFAULT 0,

    -- 計算結果
    calculated_score    INTEGER DEFAULT 0,
    risk_level          TEXT,
    force_high_risk     INTEGER DEFAULT 0,
    force_reason        TEXT,
    authenticity_probability TEXT,  -- 高/中/低
    reasoning           TEXT,

    created_at  TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at  TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 論文・資料データ
CREATE TABLE IF NOT EXISTS references_ (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    title                   TEXT NOT NULL,
    author                  TEXT,
    year                    INTEGER,
    ref_type                TEXT,   -- 論文/博物館資料/オークション資料/鑑定機関資料/市場記事
    url                     TEXT,
    pdf_path                TEXT,
    summary                 TEXT,
    key_points              TEXT,
    related_fake_features   TEXT,
    related_materials       TEXT,
    reliability             INTEGER DEFAULT 3,  -- 1-5
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP
);

-- オークション比較データ
CREATE TABLE IF NOT EXISTS auctions (
    id                      INTEGER PRIMARY KEY AUTOINCREMENT,
    auction_house           TEXT,
    lot_number              TEXT,
    item_name               TEXT,
    period                  TEXT,
    material                TEXT,
    size_description        TEXT,
    estimate_low            REAL,
    estimate_high           REAL,
    hammer_price            REAL,
    currency                TEXT DEFAULT 'JPY',
    sale_date               TEXT,
    provenance              TEXT,
    condition_description   TEXT,
    source_url              TEXT,
    image_path              TEXT,
    comparison_memo         TEXT,
    created_at              TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 偽物特徴データ
CREATE TABLE IF NOT EXISTS fake_features (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    feature_name        TEXT NOT NULL,
    target_category     TEXT,
    description         TEXT,
    observation_method  TEXT,
    judgment_basis      TEXT,
    reference_url       TEXT,
    image_example_path  TEXT,
    danger_level        INTEGER DEFAULT 3,  -- 1-5
    memo                TEXT,
    created_at          TEXT DEFAULT CURRENT_TIMESTAMP
);

-- 作品 ↔ 資料
CREATE TABLE IF NOT EXISTS item_references (
    item_id      INTEGER REFERENCES items(id) ON DELETE CASCADE,
    reference_id INTEGER REFERENCES references_(id) ON DELETE CASCADE,
    PRIMARY KEY (item_id, reference_id)
);

-- 作品 ↔ 偽物特徴
CREATE TABLE IF NOT EXISTS item_fake_features (
    item_id         INTEGER REFERENCES items(id) ON DELETE CASCADE,
    fake_feature_id INTEGER REFERENCES fake_features(id) ON DELETE CASCADE,
    match_confidence TEXT,   -- 高/中/低
    notes           TEXT,
    PRIMARY KEY (item_id, fake_feature_id)
);

-- 作品 ↔ オークション比較
CREATE TABLE IF NOT EXISTS item_auctions (
    item_id         INTEGER REFERENCES items(id) ON DELETE CASCADE,
    auction_id      INTEGER REFERENCES auctions(id) ON DELETE CASCADE,
    comparison_notes TEXT,
    PRIMARY KEY (item_id, auction_id)
);
"""
