-- ============================================================================
-- Jakarta Banking & Finance - Places Insights Demo Queries
-- Banking Industry - Competitive Intelligence Framework
-- ============================================================================
-- Current Example: Bank BCA
-- Adaptable for: Any bank in Indonesia (Mandiri, BNI, CIMB, Permata, etc.)
--
-- CUSTOMIZATION:
-- 1. Replace "BCA" with your bank name in comments
-- 2. Update table references: bca_branches → [your_bank]_branches
-- 3. Change city: Replace 'Jakarta' with any Indonesian city
-- ============================================================================
-- Project: johanesa-playground-326616
-- Dataset: places_insights___id.places
-- ============================================================================

-- ============================================================================
-- QUERY 1: Market Landscape Overview
-- Business Question: What does the financial services landscape look like?
-- ============================================================================

SELECT WITH AGGREGATION_THRESHOLD
  primary_type,
  COUNT(*) AS location_count,
  ROUND(AVG(rating), 2) AS avg_rating,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews,
  COUNTIF(rating >= 4.5) AS excellent_rated,
  ROUND(COUNTIF(rating >= 4.5) / COUNT(*) * 100, 1) AS excellent_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  ('Jakarta' IN UNNEST(locality_names)
   OR administrative_area_level_1_name LIKE '%Jakarta%')
  AND (
    'bank' IN UNNEST(types)
    OR 'atm' IN UNNEST(types)
    OR 'finance' IN UNNEST(types)
  )
  AND business_status = 'OPERATIONAL'
GROUP BY primary_type
ORDER BY location_count DESC;

-- ============================================================================
-- QUERY 2: Geographic Distribution Heatmap
-- Business Question: Where are financial services concentrated?
-- Use: BigQuery Studio Visualization (set Data Column to total_count)
-- ============================================================================

SELECT
  geo_txt,
  ST_GEOGFROMTEXT(geo_txt) AS geo,
  total_count,
  bank_count,
  atm_count,
  ROUND(avg_rating, 2) AS avg_rating
FROM (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS total_count,
    COUNTIF('bank' IN UNNEST(types)) AS bank_count,
    COUNTIF('atm' IN UNNEST(types)) AS atm_count,
    AVG(rating) AS avg_rating
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    ('Jakarta' IN UNNEST(locality_names)
     OR administrative_area_level_1_name LIKE '%Jakarta%')
    AND (
      'bank' IN UNNEST(types)
      OR 'atm' IN UNNEST(types)
    )
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
)
ORDER BY total_count DESC;

-- ============================================================================
-- QUERY 3: Quality & Service Analysis
-- Business Question: How do banks perform on quality and accessibility?
-- ============================================================================

SELECT WITH AGGREGATION_THRESHOLD
  CASE
    WHEN rating >= 4.5 THEN 'Excellent (4.5+)'
    WHEN rating >= 4.0 THEN 'Good (4.0-4.5)'
    WHEN rating >= 3.5 THEN 'Average (3.5-4.0)'
    ELSE 'Below Average (<3.5)'
  END AS rating_category,
  COUNT(*) AS bank_count,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews,
  COUNTIF(wheelchair_accessible_entrance = true) AS accessible_locations,
  ROUND(COUNTIF(wheelchair_accessible_entrance = true) / COUNT(*) * 100, 1) AS accessibility_pct,
  COUNTIF(accepts_credit_cards = true) AS card_payment_locations,
  COUNTIF(accepts_nfc = true) AS nfc_payment_locations
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  ('Jakarta' IN UNNEST(locality_names)
   OR administrative_area_level_1_name LIKE '%Jakarta%')
  AND 'bank' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND rating IS NOT NULL
GROUP BY rating_category
ORDER BY rating_category DESC;

-- ============================================================================
-- QUERY 4: White Space Opportunity Analysis
-- Business Question: Where are underserved commercial areas?
-- Use: BigQuery Studio Visualization (set Data Column to opportunity_score)
-- ============================================================================

WITH commercial_activity AS (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS total_businesses,
    COUNTIF('shopping_mall' IN UNNEST(types)
         OR 'store' IN UNNEST(types)
         OR 'restaurant' IN UNNEST(types)
         OR 'cafe' IN UNNEST(types)) AS commercial_count,
    COUNTIF('bank' IN UNNEST(types)
         OR 'atm' IN UNNEST(types)) AS financial_count
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    ('Jakarta' IN UNNEST(locality_names)
     OR administrative_area_level_1_name LIKE '%Jakarta%')
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
  HAVING commercial_count > 0
)
SELECT
  geo_txt,
  ST_GEOGFROMTEXT(geo_txt) AS geo,
  commercial_count AS commercial_businesses,
  financial_count AS existing_financial_services,
  ROUND(commercial_count / NULLIF(financial_count, 0), 2) AS opportunity_score
FROM commercial_activity
WHERE financial_count < 10      -- Low financial service presence
  AND commercial_count > 50     -- High commercial activity
ORDER BY opportunity_score DESC
LIMIT 20;

-- ============================================================================
-- QUERY 5: Regional Performance Benchmark
-- Business Question: How does quality vary across Jakarta districts?
-- ============================================================================

SELECT WITH AGGREGATION_THRESHOLD
  administrative_area_level_3_name AS district,
  COUNT(*) AS bank_count,
  ROUND(AVG(rating), 2) AS avg_rating,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews,
  COUNTIF(rating >= 4.5) AS excellent_count,
  ROUND(COUNTIF(rating >= 4.5) / COUNT(*) * 100, 1) AS excellent_pct,
  COUNTIF(wheelchair_accessible_entrance = true) AS accessible_count
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  administrative_area_level_1_name LIKE '%Jakarta%'
  AND 'bank' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND administrative_area_level_3_name IS NOT NULL
  AND rating IS NOT NULL
GROUP BY district
HAVING bank_count >= 5
ORDER BY avg_rating DESC
LIMIT 15;

-- ============================================================================
-- QUERY 6: Operating Hours Optimization
-- Business Question: When are banks open vs customer needs?
-- ============================================================================

SELECT WITH AGGREGATION_THRESHOLD
  COUNT(*) AS total_banks,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.saturday) AS hours
    WHERE hours.start_time IS NOT NULL
  )) AS saturday_service,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.sunday) AS hours
    WHERE hours.start_time IS NOT NULL
  )) AS sunday_service,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.monday) AS hours
    WHERE hours.start_time <= TIME '08:00:00'
  )) AS early_opening,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.monday) AS hours
    WHERE hours.end_time >= TIME '17:00:00'
  )) AS late_closing,
  ROUND(COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.saturday) AS hours
    WHERE hours.start_time IS NOT NULL
  )) / COUNT(*) * 100, 1) AS saturday_pct,
  ROUND(COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.sunday) AS hours
    WHERE hours.start_time IS NOT NULL
  )) / COUNT(*) * 100, 1) AS sunday_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  ('Jakarta' IN UNNEST(locality_names)
   OR administrative_area_level_1_name LIKE '%Jakarta%')
  AND 'bank' IN UNNEST(types)
  AND business_status = 'OPERATIONAL';

-- ============================================================================
-- QUERY 7: Payment Method & Technology Adoption
-- Business Question: What payment methods do financial services accept?
-- ============================================================================

SELECT WITH AGGREGATION_THRESHOLD
  COUNT(*) AS total_locations,
  COUNTIF(accepts_credit_cards = true) AS credit_cards,
  COUNTIF(accepts_debit_cards = true) AS debit_cards,
  COUNTIF(accepts_nfc = true) AS nfc_payment,
  COUNTIF(accepts_cash_only = true) AS cash_only,
  ROUND(COUNTIF(accepts_nfc = true) / COUNT(*) * 100, 1) AS nfc_adoption_pct,
  ROUND(COUNTIF(accepts_credit_cards = true) / COUNT(*) * 100, 1) AS credit_adoption_pct,
  ROUND(COUNTIF(accepts_debit_cards = true) / COUNT(*) * 100, 1) AS debit_adoption_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  ('Jakarta' IN UNNEST(locality_names)
   OR administrative_area_level_1_name LIKE '%Jakarta%')
  AND ('bank' IN UNNEST(types) OR 'atm' IN UNNEST(types))
  AND business_status = 'OPERATIONAL';

-- ============================================================================
-- BCA DATA INTEGRATION QUERIES
-- Note: Replace 'your_project.your_dataset.bca_branches' with actual table
-- ============================================================================

-- ============================================================================
-- JOIN QUERY 1: Competitors Near BCA Branches
-- Business Question: How many competitors are near each BCA branch?
-- ============================================================================

WITH bca_branches AS (
  -- BCA provides this table with: branch_id, branch_name, branch_type, latitude, longitude
  SELECT
    branch_id,
    branch_name,
    branch_type,
    ST_GEOGPOINT(longitude, latitude) AS branch_location
  FROM `your_project.your_dataset.bca_branches`
)
SELECT WITH AGGREGATION_THRESHOLD
  b.branch_id,
  b.branch_name,
  b.branch_type,
  COUNT(*) AS competitors_within_500m,
  COUNTIF('atm' IN UNNEST(p.types)) AS competitor_atms,
  COUNTIF('bank' IN UNNEST(p.types)) AS competitor_banks,
  ROUND(AVG(p.rating), 2) AS avg_competitor_rating,
  ROUND(AVG(p.user_rating_count), 1) AS avg_competitor_reviews
FROM bca_branches b
CROSS JOIN `johanesa-playground-326616.places_insights___id.places` p
WHERE
  ST_DWITHIN(b.branch_location, p.point, 500)  -- 500 meters radius
  AND ('bank' IN UNNEST(p.types) OR 'atm' IN UNNEST(p.types))
  AND p.business_status = 'OPERATIONAL'
GROUP BY b.branch_id, b.branch_name, b.branch_type
ORDER BY competitors_within_500m DESC;

-- ============================================================================
-- JOIN QUERY 2: BCA Market Share by Postal Code
-- Business Question: What's BCA's market share in each postal code?
-- ============================================================================

WITH bca_by_postal AS (
  SELECT
    postal_code,
    COUNT(*) AS bca_locations
  FROM `your_project.your_dataset.bca_branches`
  GROUP BY postal_code
),
market_by_postal AS (
  SELECT WITH AGGREGATION_THRESHOLD
    postal_code,
    COUNT(*) AS total_financial_services,
    COUNTIF('bank' IN UNNEST(types)) AS total_banks,
    COUNTIF('atm' IN UNNEST(types)) AS total_atms
  FROM `johanesa-playground-326616.places_insights___id.places`,
  UNNEST(postal_code_names) AS postal_code
  WHERE
    administrative_area_level_1_name LIKE '%Jakarta%'
    AND ('bank' IN UNNEST(types) OR 'atm' IN UNNEST(types))
    AND business_status = 'OPERATIONAL'
  GROUP BY postal_code
)
SELECT
  m.postal_code,
  COALESCE(b.bca_locations, 0) AS bca_count,
  m.total_financial_services,
  m.total_banks,
  m.total_atms,
  ROUND(COALESCE(b.bca_locations, 0) / m.total_financial_services * 100, 2) AS bca_market_share_pct,
  CASE
    WHEN COALESCE(b.bca_locations, 0) = 0 THEN 'No Presence'
    WHEN COALESCE(b.bca_locations, 0) / m.total_financial_services < 0.05 THEN 'Low (<5%)'
    WHEN COALESCE(b.bca_locations, 0) / m.total_financial_services < 0.15 THEN 'Medium (5-15%)'
    ELSE 'High (>15%)'
  END AS market_position
FROM market_by_postal m
LEFT JOIN bca_by_postal b ON m.postal_code = b.postal_code
WHERE m.total_financial_services >= 5
ORDER BY m.total_financial_services DESC;

-- ============================================================================
-- JOIN QUERY 3: White Space Without BCA Presence
-- Business Question: Where are high-opportunity areas with no BCA?
-- ============================================================================

WITH bca_coverage AS (
  SELECT DISTINCT
    ST_ASTEXT(ST_SNAPTOGRID(ST_GEOGPOINT(longitude, latitude), 0.01)) AS geo_grid
  FROM `your_project.your_dataset.bca_branches`
),
market_opportunities AS (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS total_businesses,
    COUNTIF('shopping_mall' IN UNNEST(types)
         OR 'store' IN UNNEST(types)
         OR 'restaurant' IN UNNEST(types)) AS commercial_count,
    COUNTIF('bank' IN UNNEST(types)
         OR 'atm' IN UNNEST(types)) AS financial_count
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    administrative_area_level_1_name LIKE '%Jakarta%'
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
  HAVING commercial_count > 50 AND financial_count < 10
)
SELECT
  m.geo_txt,
  ST_GEOGFROMTEXT(m.geo_txt) AS geo,
  m.commercial_count,
  m.financial_count,
  ROUND(m.commercial_count / NULLIF(m.financial_count, 0), 2) AS opportunity_score,
  'No BCA Presence' AS bca_status
FROM market_opportunities m
LEFT JOIN bca_coverage b ON m.geo_txt = b.geo_grid
WHERE b.geo_grid IS NULL  -- Areas where BCA has NO presence
ORDER BY opportunity_score DESC
LIMIT 20;

-- ============================================================================
-- JOIN QUERY 4: BCA Performance vs Local Competition
-- Business Question: How do BCA branches perform vs nearby competitors?
-- ============================================================================

WITH bca_branches AS (
  SELECT
    branch_id,
    branch_name,
    bca_rating,  -- BCA's internal rating if available
    ST_GEOGPOINT(longitude, latitude) AS location
  FROM `your_project.your_dataset.bca_branches`
),
local_competition AS (
  SELECT WITH AGGREGATION_THRESHOLD
    b.branch_id,
    b.branch_name,
    b.bca_rating,
    COUNT(*) AS nearby_competitors,
    ROUND(AVG(p.rating), 2) AS avg_competitor_rating,
    ROUND(AVG(p.user_rating_count), 1) AS avg_competitor_reviews
  FROM bca_branches b
  CROSS JOIN `johanesa-playground-326616.places_insights___id.places` p
  WHERE
    ST_DWITHIN(b.location, p.point, 1000)
    AND 'bank' IN UNNEST(p.types)
    AND p.business_status = 'OPERATIONAL'
    AND p.rating IS NOT NULL
  GROUP BY b.branch_id, b.branch_name, b.bca_rating
)
SELECT
  branch_id,
  branch_name,
  bca_rating,
  avg_competitor_rating,
  nearby_competitors,
  ROUND(bca_rating - avg_competitor_rating, 2) AS rating_advantage,
  CASE
    WHEN bca_rating > avg_competitor_rating + 0.3 THEN 'Outperforming'
    WHEN bca_rating < avg_competitor_rating - 0.3 THEN 'Underperforming'
    ELSE 'Competitive'
  END AS performance_status
FROM local_competition
ORDER BY rating_advantage DESC;

-- ============================================================================
-- END OF QUERIES
-- ============================================================================
