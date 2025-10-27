# Jakarta Banking & Finance - Places Insights Demo
## Banking Industry - Competitive Intelligence Framework

**Current Example Customer:** Bank BCA
**Adaptable for:** Any bank in Indonesia (Mandiri, BNI, CIMB, Permata, etc.)

---

## Quick Customization Guide

**To adapt this demo for another bank:**

1. **Replace Bank Name:** Find/replace "BCA" with your bank name throughout
2. **Update Table References:** Change `bca_branches` to `[your_bank]_branches` in join queries
3. **Adjust Talking Points:** Customize strategic recommendations to your bank's context
4. **Change City (Optional):** Replace "Jakarta" with any Indonesian city in the dataset

**Demo Variables:**
- **Bank Name:** BCA *(change as needed)*
- **Target City:** Jakarta *(change as needed)*
- **Branch Table:** `your_project.your_dataset.bca_branches` *(update project/dataset/table)*

---

## Table of Contents
1. [Demo Overview](#demo-overview)
2. [Understanding the Data](#understanding-the-data)
3. [Demo Flow](#demo-flow)
4. [Query 1: Market Landscape](#query-1-market-landscape)
5. [Query 2: Geographic Heatmap](#query-2-geographic-heatmap)
6. [Query 3: Quality & Service Analysis](#query-3-quality--service-analysis)
7. [Query 4: White Space Opportunities](#query-4-white-space-opportunities)
8. [Query 5: Regional Performance](#query-5-regional-performance)
9. [Query 6: Operating Hours Optimization](#query-6-operating-hours-optimization)
10. [Query 7: Payment Method & Technology Adoption](#query-7-payment-method--technology-adoption)
11. [Integrating Your Bank's Data](#integrating-your-banks-data)
12. [Visualization Guide](#visualization-guide)
13. [Presentation Tips](#presentation-tips)

---

## Demo Overview

### Business Objective
Demonstrate how Places Insights can provide competitive intelligence for **any bank** to:
- Understand the competitive landscape in target cities
- Identify market gaps and expansion opportunities
- Benchmark service quality across the market
- Make data-driven decisions for branch/ATM placement

**Example Customer:** Bank BCA analyzing Jakarta market

### Key Metrics (Jakarta Example)
- **9,434 ATMs** in Jakarta
- **7,028 Banks** in Jakarta
- **6,191 Finance companies** in Jakarta
- Coverage across all Jakarta districts

**Note:** *These metrics can be generated for any Indonesian city in the dataset (Surabaya, Bandung, Medan, etc.)*

### Data Limitations & Opportunities

**❌ What We CANNOT Do:**
- Identify specific bank brands (BCA, Mandiri, BNI) - no brands dataset for Indonesia
- Show foot traffic or visitor counts - not in Places Insights
- Access demographic data - requires separate Area Insights API
- Show time-series trends - static snapshot data

**✅ What We CAN Do:**
- Map competitive density across any city
- Analyze quality metrics (ratings, reviews)
- Identify underserved commercial areas
- Benchmark service characteristics
- **Join with your bank's internal data** for competitive positioning

**Example:** *BCA can overlay their branch locations to see competitive positioning*

---

## Understanding the Data

### Dataset Information
- **Project:** `johanesa-playground-326616`
- **Dataset:** `places_insights___id.places`
- **Region:** Indonesia (Jakarta focus)
- **Location:** US (BigQuery dataset location)

### Key Schema Fields for Analysis

**Location Fields:**
- `point` (GEOGRAPHY) - Geographic point
- `location.latitude` (FLOAT)
- `location.longitude` (FLOAT)

**Identification:**
- `id` (STRING) - Google Place ID
- `types` (ARRAY<STRING>) - Place types
- `primary_type` (STRING) - Primary classification

**Quality Metrics:**
- `rating` (FLOAT) - 1.0 to 5.0
- `user_rating_count` (INTEGER)
- `business_status` (STRING) - OPERATIONAL, CLOSED_TEMPORARILY, CLOSED_PERMANENTLY

**Geographic Boundaries:**
- `locality_names` (ARRAY<STRING>)
- `postal_code_names` (ARRAY<STRING>)
- `administrative_area_level_1_name` through `_level_7_name`

**Service Attributes:**
- `wheelchair_accessible_entrance` (BOOLEAN)
- `accepts_credit_cards`, `accepts_nfc` (BOOLEAN)
- `regular_opening_hours` (RECORD)

---

## Demo Flow

### Recommended Presentation Structure

**Act 1: The Big Picture (5 minutes)**
- Query 1: Market Landscape
- Show total market size and composition

**Act 2: Where's the Action? (7 minutes)**
- Query 2: Geographic Heatmap
- Visualize concentration areas
- Identify saturated vs sparse regions

**Act 3: Quality Matters (5 minutes)**
- Query 3: Quality & Service Analysis
- Benchmark performance standards
- Highlight accessibility gaps

**Act 4: The Opportunity (8 minutes)**
- Query 4: White Space Analysis
- Identify underserved commercial areas
- Quantify expansion opportunities

**Act 5: Regional & Service Analysis (8 minutes)**
- Query 5: Regional Performance
- Query 6: Operating Hours Optimization
- Query 7: Payment Method Adoption

**Act 6: BCA's Position (10 minutes)**
- Integration examples with BCA data
- Competitive positioning
- Strategic recommendations

**Total: ~43 minutes + Q&A**

### Enhanced Demo Features

**New Additions:**
1. **Operating Hours Analysis** - Reveals 83% of banks closed on weekends
2. **Payment Technology** - Shows only 3% report NFC capability
3. **Comprehensive Coverage** - 7 core queries vs original 5

**Strategic Value:**
- More complete competitive intelligence
- Customer convenience insights
- Digital transformation opportunities

---

## Query 1: Market Landscape

### Business Question
*"What does the financial services landscape look like in Jakarta?"*

### The Query

```sql
-- Market Overview: Financial Services Distribution in Jakarta
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
ORDER BY location_count DESC
```

### Expected Results

| primary_type | location_count | avg_rating | avg_reviews | excellent_rated | excellent_pct |
|--------------|----------------|------------|-------------|-----------------|---------------|
| atm | 9,434 | - | - | - | - |
| bank | 7,028 | 4.2 | 28.5 | ~3,200 | ~46% |
| finance | 6,191 | - | - | - | - |

### Talking Points

1. **Market Size:** "Jakarta has over 16,000 financial service locations"
2. **ATM Dominance:** "ATMs outnumber bank branches, showing customer preference for self-service"
3. **Quality Bar:** "46% of banks achieve excellent ratings (4.5+), setting a high competitive standard"
4. **Opportunity:** "This is the competitive landscape BCA operates in"

### Next Step
→ "Now let's see WHERE these services are concentrated..."

---

## Query 2: Geographic Heatmap

### Business Question
*"Where are financial services concentrated in Jakarta?"*

### The Query

```sql
-- Geographic Distribution: Density Heatmap
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
ORDER BY total_count DESC
```

### Visualization in BigQuery Studio

**Step-by-Step:**

1. **Run the query** in BigQuery Studio
2. Click the **"Visualization"** tab at the bottom
3. Under "Visualization configuration":
   - Set **Data Column** to `total_count`
   - Adjust **Color scheme** to "Red-Yellow-Green" or "Viridis"
   - Set **Circle radius** to 15-20 for better visibility
4. **Interpret the map:**
   - Darker/larger circles = higher concentration
   - Lighter/smaller circles = lower concentration

### Expected Insights

**Top Concentration Areas:**
- Central Jakarta (106.82, -6.19): 280 locations
- Business districts show highest density
- Residential areas show moderate density
- Peripheral areas show sparse coverage

### Talking Points

1. **Saturation:** "Central Jakarta is highly saturated with 280+ financial services in some grid cells"
2. **Competition:** "These dark areas represent intense competition"
3. **Gaps:** "Notice the lighter areas - potential opportunities"
4. **Strategy:** "BCA needs to decide: compete in saturated areas or target gaps?"

### Next Step
→ "Let's understand the quality standards in this market..."

---

## Query 3: Quality & Service Analysis

### Business Question
*"How do banks perform on quality and accessibility?"*

### The Query

```sql
-- Quality Analysis: Rating Distribution and Service Characteristics
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
ORDER BY rating_category DESC
```

### Expected Results

| rating_category | bank_count | avg_reviews | accessible_locations | accessibility_pct |
|-----------------|------------|-------------|----------------------|-------------------|
| Excellent (4.5+) | 2,126 | 40.1 | 163 | 7.7% |
| Good (4.0-4.5) | 982 | 32.3 | 119 | 12.1% |
| Average (3.5-4.0) | 563 | 23.4 | 73 | 13.0% |
| Below Average (<3.5) | 1,034 | 13.9 | 76 | 7.4% |

### Talking Points

1. **Quality Distribution:** "46% of banks achieve excellent ratings - this is the competitive standard"
2. **Review Correlation:** "Excellent banks average 40 reviews vs 14 for below-average - engagement matters"
3. **Accessibility Gap:** "Only 9% report accessibility features - opportunity for differentiation"
4. **Customer Expectations:** "Customers expect 4.5+ ratings and modern payment options"

### Key Insights

- **Quality Bar is High:** Nearly half of competitors are excellent
- **Reviews Matter:** More reviews correlate with higher ratings
- **Service Gaps:** Accessibility data is sparse - potential differentiator
- **BCA Benchmark:** Compare BCA's ratings against these standards

### Next Step
→ "Now let's find the opportunities - where should BCA expand?"

---

## Query 4: White Space Opportunities

### Business Question
*"Where are the underserved commercial areas with expansion potential?"*

### The Query

```sql
-- White Space Analysis: High Commercial Activity + Low Financial Service Presence
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
LIMIT 20
```

### Visualization in BigQuery Studio

1. Run the query
2. Click **"Visualization"** tab
3. Set **Data Column** to `opportunity_score`
4. Use **Red color scheme** (higher score = hotter opportunity)

### Expected Results

| geo_txt | commercial_businesses | existing_financial_services | opportunity_score |
|---------|----------------------|----------------------------|-------------------|
| POINT(106.9 -6.31) | 382 | 1 | 382.0 |
| POINT(106.93 -6.21) | 1,129 | 3 | 376.3 |
| POINT(106.69 -6.17) | 343 | 1 | 343.0 |

### Talking Points

1. **Opportunity Score:** "Score of 382 means 382 businesses per financial service - massive underserved demand"
2. **Top Opportunity:** "Area at 106.93, -6.21 has 1,129 businesses but only 3 banks/ATMs"
3. **Strategic Value:** "These are proven commercial areas with established foot traffic"
4. **Low Competition:** "First-mover advantage in these underserved zones"

### Strategic Recommendations

**Tier 1 Opportunities (Score > 300):**
- Immediate expansion targets
- High commercial activity, minimal competition
- Quick market share capture potential

**Tier 2 Opportunities (Score 150-300):**
- Medium-term expansion
- Growing commercial areas
- Moderate competition

**Tier 3 Opportunities (Score 50-150):**
- Long-term consideration
- Emerging commercial zones
- Monitor for growth

### Next Step
→ "Let's see how performance varies across Jakarta districts..."

---

## Query 5: Regional Performance

### Business Question
*"How does banking service quality vary across Jakarta districts?"*

### The Query

```sql
-- Regional Performance Benchmark
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
LIMIT 15
```

### Talking Points

1. **District Variation:** "Quality varies significantly by district"
2. **Premium Areas:** "Highest-rated districts likely serve affluent customers"
3. **Opportunity Districts:** "Lower-rated districts may have service gaps"
4. **BCA Strategy:** "Match BCA's service level to district expectations"

### Next Step
→ "Let's analyze when banks are available to serve customers..."

---

## Query 6: Operating Hours Optimization

### Business Question
*"When are banks open vs customer needs?"*

### The Query

```sql
-- Banking Hours Analysis
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
  AND business_status = 'OPERATIONAL'
```

### Expected Results

| total_banks | saturday_service | sunday_service | saturday_pct | sunday_pct |
|-------------|------------------|----------------|--------------|------------|
| 7,320 | 1,236 | 1,039 | 16.9% | 14.2% |

### Talking Points

1. **Weekend Gap:** "Only 17% of banks open on Saturday - major customer convenience gap"
2. **Sunday Service:** "14% offer Sunday service - opportunity for differentiation"
3. **Customer Needs:** "Working customers need weekend banking access"
4. **BCA Advantage:** "Extended hours = competitive advantage"

### Key Insights

- **Limited Weekend Service:** 83% of banks closed on Saturday
- **Customer Inconvenience:** Forces customers to take time off work
- **Opportunity:** BCA can differentiate with extended hours
- **ATM Reliance:** Customers forced to use ATMs for weekend needs

### Next Step
→ "Now let's examine payment technology adoption..."

---

## Query 7: Payment Method & Technology Adoption

### Business Question
*"What payment methods do financial services accept?"*

### The Query

```sql
-- Payment Method Analysis
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
  AND business_status = 'OPERATIONAL'
```

### Expected Results

| total_locations | credit_cards | debit_cards | nfc_payment | nfc_adoption_pct |
|-----------------|--------------|-------------|-------------|------------------|
| 17,135 | 512 | 527 | 510 | 3.0% |

### Talking Points

1. **Low Digital Adoption:** "Only 3% report NFC payment capability"
2. **Data Gap:** "Most locations don't report payment methods - opportunity to lead"
3. **Technology Lag:** "Digital payment infrastructure needs improvement"
4. **BCA Leadership:** "BCA can set the standard for digital payment adoption"

### Key Insights

- **Sparse Data:** Only ~3% of locations report payment methods
- **Digital Opportunity:** Low NFC adoption shows room for innovation
- **Customer Expectation:** Modern customers expect contactless payment
- **Competitive Edge:** Early digital adopters gain customer preference

### Strategic Implications

**For BCA:**
1. **Lead Digital Transformation:** Be first to offer comprehensive NFC
2. **Customer Education:** Promote digital payment benefits
3. **Infrastructure Investment:** Upgrade all touchpoints
4. **Marketing Advantage:** "Most modern banking experience in Jakarta"

---

## Integrating Your Bank's Data

**Example:** Using BCA branch data for competitive positioning

### Why Join Your Bank's Data?

**Transform from Market Intelligence to Competitive Positioning:**
- "Here's the market" → "Here's where [Your Bank] stands"
- "Here are opportunities" → "Here's where [Your Bank] should expand"
- "Here's the competition" → "Here's [Your Bank] vs competitors"

**BCA Example:** *"Here's where BCA stands in Jakarta's competitive landscape"*

### What Your Bank Needs to Provide

**Minimum Required Data:**
```
branch_id, branch_name, latitude, longitude
```

**Enhanced Data (Optional):**
```
branch_id, branch_name, branch_type, latitude, longitude,
opening_date, services_offered, transaction_volume, customer_count
```

**Note:** *Replace `bca_branches` with `[your_bank]_branches` in all queries below*

### Join Strategy 1: Spatial Proximity Analysis

**Business Question:** *"How many competitors are near each BCA branch?"*

```sql
-- Find Competitors Within 500m of Each BCA Branch
WITH bca_branches AS (
  -- BCA provides this table
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
ORDER BY competitors_within_500m DESC
```

**Insights:**
- Identify BCA's most competitive locations
- Benchmark BCA against nearby competitors
- Prioritize branches needing service improvements

### Join Strategy 2: Market Share by Postal Code

**Business Question:** *"What's BCA's market share in each postal code?"*

```sql
-- BCA Market Share Analysis by Postal Code
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
ORDER BY m.total_financial_services DESC
```

**Insights:**
- Identify strong vs weak postal codes
- Target underrepresented areas
- Defend high-share territories

### Join Strategy 3: White Space for BCA Expansion

**Business Question:** *"Where are high-opportunity areas with no BCA presence?"*

```sql
-- High-Opportunity Areas Without BCA Presence
WITH bca_coverage AS (
  SELECT DISTINCT
    ST_ASTEXT(ST_SNAPTOGRID(ST_GEOGPOINT(longitude, latitude), 0.01)) AS geo_grid
  FROM `your_project.your_dataset.bca_branches`
),
market_opportunities AS (
  -- Use the White Space query from Query 4
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
LIMIT 20
```

**Strategic Output:**
- Prioritized expansion targets
- Quantified opportunity (commercial activity)
- Competitive gap analysis

### Join Strategy 4: Performance Benchmarking

**Business Question:** *"How do BCA branches perform vs nearby competitors?"*

```sql
-- BCA Branch Performance vs Local Competition
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
ORDER BY rating_advantage DESC
```

**Actionable Insights:**
- Identify underperforming branches
- Replicate success from outperforming branches
- Prioritize improvement initiatives

---

## Visualization Guide

### BigQuery Studio Visualizations

**For Geographic Queries (Query 2, 4):**

1. **Run the query** with geography column
2. Click **"Visualization"** tab
3. **Configure:**
   - Data Column: `total_count` or `opportunity_score`
   - Color Scheme: Choose based on message
     - Red-Yellow-Green: Good for opportunity (green = good)
     - Viridis: Good for density (dark = high)
     - Red: Good for heat/intensity
   - Circle Radius: 15-20 pixels
   - Opacity: 70-80%

4. **Interpret:**
   - Larger/darker circles = higher values
   - Cluster patterns show concentration
   - Gaps show opportunities

**For Tabular Results (Query 1, 3, 5):**

Export to Google Sheets or Looker Studio for:
- Bar charts (counts, comparisons)
- Pie charts (distribution)
- Tables (detailed breakdowns)

### Looker Studio Integration

**Step 1: Connect to BigQuery**
1. Open Looker Studio
2. Create new report
3. Add data source → BigQuery
4. Select "Custom Query"
5. Paste your SQL query

**Step 2: Create Visualizations**

**For Query 1 (Market Overview):**
- Bar chart: primary_type vs location_count
- Scorecard: Total locations
- Table: Detailed breakdown

**For Query 2 (Geographic):**
- Bubble map: geo column, size by total_count
- Heatmap: Color by density

**For Query 3 (Quality):**
- Pie chart: Rating category distribution
- Bar chart: Rating vs review count
- Scorecard: % Excellent rated

**For Query 4 (White Space):**
- Bubble map: Opportunity score
- Table: Top 20 opportunities
- Scatter plot: Commercial vs Financial count

---

## Presentation Tips

### Opening (2 minutes)

**Hook:**
> "Jakarta has over 16,000 financial service locations. The question isn't whether there's competition - it's where BCA should compete and where BCA can dominate."

**Agenda:**
1. Market landscape
2. Geographic concentration
3. Quality benchmarks
4. Expansion opportunities
5. BCA's strategic position

### During the Demo

**Do:**
- ✅ Start with big picture, narrow to specifics
- ✅ Use concrete numbers ("382 businesses per bank")
- ✅ Pause for questions after each query
- ✅ Connect insights to BCA strategy
- ✅ Show visualizations, not just tables

**Don't:**
- ❌ Dive into SQL syntax
- ❌ Apologize for data limitations
- ❌ Show errors or failed queries
- ❌ Rush through visualizations
- ❌ Ignore audience questions

### Key Messages

**Message 1: Market is Competitive**
- "7,028 banks compete for Jakarta customers"
- "46% achieve excellent ratings - the bar is high"

**Message 2: Geography Matters**
- "Central Jakarta is saturated - 280 services in one grid cell"
- "Peripheral areas show opportunity"

**Message 3: Quality is Table Stakes**
- "Customers expect 4.5+ ratings"
- "Excellent banks get 3x more reviews"

**Message 4: White Space Exists**
- "1,129 businesses served by only 3 banks"
- "Proven commercial areas, minimal competition"

**Message 5: Data Drives Decisions**
- "With BCA's data, we can pinpoint exactly where to expand"
- "This is competitive intelligence, not guesswork"

### Handling Questions

**Q: "Can we see BCA's specific locations?"**
A: "Not in this aggregated view due to privacy protections, but we can overlay BCA's internal data to show your competitive position. That's actually more powerful - you see the market AND your position."

**Q: "How current is this data?"**
A: "Places Insights is updated regularly from Google Maps. For real-time foot traffic, we'd integrate Area Insights API."

**Q: "Can we identify specific competitors like Mandiri?"**
A: "The brands dataset is US-only currently. However, we can analyze by location proximity - if BCA knows where Mandiri branches are, we can benchmark against them."

**Q: "What about customer demographics?"**
A: "Demographics require Area Insights API. Today we're showing location intelligence - where to be. Area Insights would add who to serve."

### Closing (3 minutes)

**Summary:**
> "We've shown you the competitive landscape, identified white space opportunities, and demonstrated how BCA's data transforms this from market intelligence to strategic advantage."

**Call to Action:**
1. "Provide BCA branch/ATM data for competitive positioning"
2. "Prioritize top 5 white space opportunities for expansion"
3. "Benchmark BCA's ratings against local competition"
4. "Develop district-specific strategies based on performance data"

**Final Thought:**
> "Every bank has branches. BCA can have branches in the RIGHT places, backed by data."

---

## Technical Notes

### Query Performance

**Optimization Tips:**
- Use `LIMIT` for initial testing
- Grid size (0.01 degrees ≈ 1.1km) balances detail vs performance
- `WITH AGGREGATION_THRESHOLD` is required for privacy
- Results only returned if count ≥ 5

### Common Issues

**Issue: "Query returns no results"**
- Check `business_status = 'OPERATIONAL'`
- Verify location filters (Jakarta spelling)
- Ensure aggregation threshold is met (count ≥ 5)

**Issue: "Visualization not showing"**
- Confirm geography column is named `geo`
- Check data column is numeric
- Verify results have geographic data

**Issue: "Join returns no matches"**
- Verify coordinate precision matches
- Check for NULL values
- Ensure grid size alignment

### Data Refresh

- Places Insights updates regularly
- For latest data, re-run queries
- Consider scheduling queries for monitoring

---

## Next Steps

### Immediate Actions

1. **Run all 5 queries** in BigQuery Studio
2. **Create visualizations** for Query 2 and 4
3. **Export results** to Google Sheets
4. **Practice the demo flow** (35 minutes)

### With BCA Data

1. **Collect BCA branch/ATM data** (branch_id, name, lat, long)
2. **Upload to BigQuery** as a table
3. **Run join queries** (proximity, market share, white space)
4. **Create competitive positioning** visualizations

### Advanced Analysis

1. **Area Insights API** for foot traffic data
2. **Time-series analysis** with scheduled queries
3. **Predictive modeling** for expansion ROI
4. **Custom dashboards** in Looker Studio

---

## Resources

### Documentation
- [Places Insights Overview](https://developers.google.com/maps/documentation/placesinsights)
- [BigQuery Geospatial Functions](https://cloud.google.com/bigquery/docs/reference/standard-sql/geography_functions)
- [Looker Studio](https://lookerstudio.google.com/)

### Support
- BigQuery Console: https://console.cloud.google.com/bigquery
- Places Insights Dataset: `johanesa-playgroun
