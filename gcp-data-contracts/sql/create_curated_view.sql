-- =============================================================================
-- Curated Analytical Data Contract View (Grade A Certified)
-- Generated from contract.odcs.yaml + config/business_glossary.yaml
-- Do not edit manually; run: python3 scripts/provision_catalog.py render-sql
-- =============================================================================
CREATE OR REPLACE VIEW `${PROJECT_ID}.sgx_market_data.equity_trades_curated` (
    trade_id OPTIONS(description="[Inherited: Upstream Source Dictionary] (FIX 4.2 Tag 17 (ExecID) / contract.odcs.yaml#trade_id) Unique trade execution identifier (e.g. TR-SGX-20260914-001) assigned deterministically by the Exchange Order Matching Engine upon order match. Required primary key; must not be null."),
    instrument_code OPTIONS(description="[Inherited: Upstream Source Dictionary] (FIX 4.2 Tag 48 (SecurityID) / contract.odcs.yaml#instrument_code) Exchange-listed security ticker symbol (e.g. D05.SI, Z74.SI, O39.SI) identifying the traded equity instrument. Required field; must not be null."),
    price OPTIONS(description="[Inherited: Upstream Source Dictionary] (FIX 4.2 Tag 31 (LastPx) / contract.odcs.yaml#price) Executed trade price per share in settlement currency (NUMERIC). Must not be null and must be strictly positive (price > 0)."),
    volume OPTIONS(description="[Inherited: Upstream Source Dictionary] (FIX 4.2 Tag 32 (LastQty) / contract.odcs.yaml#volume) Number of shares matched in the execution event (INT64). Must not be null and must be strictly positive (volume > 0)."),
    buyer_id OPTIONS(description="[Inherited: Upstream Source Dictionary] (Clearing Member Buy Account / contract.odcs.yaml#buyer_id) Clearing member participant identifier on the buy side of the matched trade. Subject to the anti-wash-trading integrity assertion (buyer_id != seller_id)."),
    seller_id OPTIONS(description="[Inherited: Upstream Source Dictionary] (Clearing Member Sell Account / contract.odcs.yaml#seller_id) Clearing member participant identifier on the sell side of the matched trade. Subject to the anti-wash-trading integrity assertion (buyer_id != seller_id)."),
    trade_timestamp OPTIONS(description="[Inherited: Upstream Source Dictionary] (FIX 4.2 Tag 60 (TransactTime UTC) / contract.odcs.yaml#trade_timestamp) UTC timestamp recorded by the Exchange Matching Engine at order execution. Governed by the 2-hour freshness SLA (trade_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR))."),
    trade_status OPTIONS(description="[Inherited: Upstream Source Dictionary] (Lifecycle Status Enum / contract.odcs.yaml#trade_status) Lifecycle state of the execution event. Must belong to the permitted contract enumeration: EXECUTED, CANCELLED, or AMENDED."),
    notional_value OPTIONS(description="[Platform-Derived: Steward Authored (AI-Assisted Pattern)] (Curated View Expression: ROUND(price * volume, 2)) Gross settlement notional value (NUMERIC) computed in the curated warehouse view as ROUND(price * volume, 2). Illustrates the governance separation where platform-derived analytical columns use steward-approved AI-assisted documentation while upstream wire fields remain 100% locked to the Source Dictionary."),
    wash_trade_flag OPTIONS(description="[Platform-Derived: Steward Authored (AI-Assisted Pattern)] (Curated View Expression: (buyer_id = seller_id)) Boolean surveillance indicator computed as (buyer_id = seller_id). Always evaluates to FALSE on certified rows inside equity_trades_curated (since self-matches are excluded by the view's WHERE buyer_id != seller_id predicate) and TRUE when evaluated on uncurated wash-trade rows in equity_trades.")
)
OPTIONS(
    description="Contract-certified Grade-A analytical view enforcing all 9 ODCS data quality rules (including the rolling 2-hour freshness SLA and anti-wash-trading integrity check) plus 2 platform-derived columns (notional_value, wash_trade_flag). Recommended primary asset for business consumers.",
    labels=[("domain", "equities_market"), ("contract_version", "1_0_0"), ("quality_grade", "grade_a"), ("governance_layer", "curated_contract_view")]
)
AS
SELECT
    trade_id,
    instrument_code,
    price,
    volume,
    buyer_id,
    seller_id,
    trade_timestamp,
    trade_status,
    ROUND(price * volume, 2) AS notional_value,
    (buyer_id = seller_id) AS wash_trade_flag
FROM `${PROJECT_ID}.sgx_market_data.equity_trades`
WHERE
    trade_id IS NOT NULL
    AND instrument_code IS NOT NULL
    AND price IS NOT NULL
    AND price > 0
    AND volume IS NOT NULL
    AND volume > 0
    AND buyer_id IS NOT NULL
    AND seller_id IS NOT NULL
    AND buyer_id != seller_id
    AND trade_status IN ('EXECUTED', 'CANCELLED', 'AMENDED')
    AND trade_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR);
