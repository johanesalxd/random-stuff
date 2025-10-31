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
- **Project:** `your-project-id`
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
FROM `your-project-id.places_insights___id.places`
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

### Actual Results

| primary_type | location_count | avg_rating | avg_reviews | excellent_rated | excellent_pct |
|--------------|----------------|------------|-------------|-----------------|---------------|
| atm | 9,434 | 4.01 | 3.1 | 1,870 | 19.8% |
| bank | 7,028 | 4.06 | 30.5 | 2,014 | 28.7% |
| finance | 6,191 | 4.28 | 33.6 | 2,062 | 33.3% |

### Key Insights

1. **Market Size:** Jakarta has 22,653 operational financial service locations (9,434 ATMs + 7,028 banks + 6,191 finance companies)
2. **ATM Dominance:** ATMs outnumber bank branches by 34%, indicating strong customer preference for self-service banking
3. **Quality Hierarchy:** Finance companies lead in quality (4.28 avg rating, 33.3% excellent) > Banks (4.06, 28.7%) > ATMs (4.01, 19.8%)
4. **Review Engagement:** Finance companies average 33.6 reviews vs banks at 30.5, showing higher customer engagement
5. **Excellence Gap:** Only 28.7% of banks achieve excellent ratings (4.5+), leaving significant room for differentiation

### Talking Points

1. **Market Scale:** "Jakarta's financial services market has over 22,000 operational locations - one of Southeast Asia's most competitive markets"
2. **Self-Service Trend:** "ATMs outnumber branches by 34%, reflecting customer preference for 24/7 self-service access"
3. **Quality Benchmark:** "The average bank rating is 4.06, with only 29% achieving excellence - there's clear opportunity to stand out through superior service"
4. **Customer Engagement:** "Banks with higher ratings average 30+ reviews, showing that quality drives customer engagement and word-of-mouth"

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
  FROM `your-project-id.places_insights___id.places`
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
   - Set **Point size** to 15-20 for better visibility
4. **Interpret the map:**
   - Darker/larger circles = higher concentration
   - Lighter/smaller circles = lower concentration

### Actual Results (Top 10 Concentration Areas)

| Location | Total | Banks | ATMs | Avg Rating |
|----------|-------|-------|------|------------|
| POINT(106.82 -6.19) | 280 | 132 | 206 | 4.06 |
| POINT(106.82 -6.14) | 216 | 120 | 140 | 4.13 |
| POINT(106.82 -6.21) | 196 | 105 | 127 | 4.09 |
| POINT(106.83 -6.14) | 192 | 102 | 123 | 3.98 |
| POINT(106.8 -6.24) | 181 | 71 | 137 | 4.15 |

### Key Insights

1. **Extreme Concentration:** The densest area (106.82, -6.19) has 280 financial services in a ~1.1km² grid - averaging 1 location per 4,000m²
2. **ATM-Heavy Zones:** Top areas have 1.5-1.9x more ATMs than branches, showing strong self-service infrastructure
3. **Quality Variation:** Dense areas range from 3.98 to 4.15 average rating - saturation doesn't guarantee quality
4. **Central Jakarta Dominance:** All top 10 locations cluster around 106.8-106.83 longitude, -6.14 to -6.24 latitude (Central/South Jakarta)
5. **Competition Intensity:** Top 5 areas alone contain 1,065 financial services - representing 6.2% of Jakarta's total in just 5 grid cells

### Talking Points

1. **Market Saturation:** "The most competitive area has 280 financial services in just 1.1km² - that's one location every 50 meters"
2. **Geographic Clustering:** "Financial services concentrate heavily in Central and South Jakarta business districts"
3. **Strategic Choice:** "Banks must decide: compete in these saturated zones with 200+ competitors, or target underserved areas"
4. **Quality Opportunity:** "Even in dense areas, ratings vary by 0.17 points - there's room to differentiate through superior service"

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
FROM `your-project-id.places_insights___id.places`
WHERE
  ('Jakarta' IN UNNEST(locality_names)
   OR administrative_area_level_1_name LIKE '%Jakarta%')
  AND 'bank' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND rating IS NOT NULL
GROUP BY rating_category
ORDER BY rating_category DESC
```

### Actual Results

| rating_category | bank_count | avg_reviews | accessible_locations | accessibility_pct | card_payment | nfc_payment |
|-----------------|------------|-------------|----------------------|-------------------|--------------|-------------|
| Excellent (4.5+) | 2,126 | 40.1 | 163 | 7.7% | 0 | 3 |
| Good (4.0-4.5) | 982 | 32.3 | 119 | 12.1% | 0 | 0 |
| Average (3.5-4.0) | 563 | 23.4 | 73 | 13.0% | 2 | 2 |
| Below Average (<3.5) | 1,034 | 13.9 | 76 | 7.4% | 1 | 2 |

### Key Insights

1. **Quality Distribution:** 45.5% of banks achieve excellent (4.5+) or good (4.0-4.5) ratings - high competitive bar
2. **Review Engagement Gap:** Excellent banks average 40.1 reviews vs 13.9 for below-average - nearly 3x difference
3. **Accessibility Paradox:** Good-rated banks show highest accessibility (12.1%) while excellent-rated show lowest (7.7%)
4. **Payment Data Scarcity:** Only 7 total locations report payment methods across 4,705 banks - 0.15% data coverage
5. **Quality Spread:** 22% of banks fall below average (<3.5 rating) - significant underperformance segment

### Talking Points

1. **Competitive Standard:** "Nearly half of Jakarta's banks achieve good or excellent ratings - the quality bar is high and customers have many options"
2. **Engagement Drives Ratings:** "Excellent banks average 40 reviews compared to 14 for below-average - customer engagement strongly correlates with quality"
3. **Accessibility Opportunity:** "Only 9.3% of banks report accessibility features - this represents a major differentiation opportunity for banks targeting inclusive service"
4. **Data Transparency Gap:** "Less than 1% of banks report payment methods - early adopters who publicize digital capabilities can gain competitive advantage"

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
  FROM `your-project-id.places_insights___id.places`
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

### Actual Results (Top 20 White Space Opportunities)

| geo_txt | commercial_businesses | existing_financial_services | opportunity_score |
|---------|----------------------|----------------------------|-------------------|
| POINT(106.9 -6.31) | 401 | 1 | 401.0 |
| POINT(106.93 -6.21) | 1,170 | 3 | 390.0 |
| POINT(106.69 -6.17) | 364 | 1 | 364.0 |
| POINT(106.74 -6.17) | 306 | 1 | 306.0 |
| POINT(106.94 -6.13) | 248 | 1 | 248.0 |

### Key Insights

1. **Extreme Opportunity:** Top location (106.9, -6.31) has 401 commercial businesses but only 1 financial service - 401:1 ratio
2. **Massive Underserved Area:** Second-ranked area (106.93, -6.21) has 1,170 businesses with just 3 banks/ATMs - serving 390 businesses each
3. **Geographic Spread:** Top opportunities span from West (106.69) to East (106.96) Jakarta - not concentrated in one area
4. **Proven Commercial Zones:** All top 20 areas have 50+ commercial establishments - these are active business districts, not emerging areas
5. **Low Competition Advantage:** 15 of top 20 areas have ≤2 financial services - first movers can capture significant market share

### Talking Points

1. **Quantified Opportunity:** "The top white space area has 401 businesses per financial service - that's 401 potential customers sharing one bank or ATM"
2. **Scale of Underservice:** "Our #2 opportunity has 1,170 commercial businesses served by only 3 financial locations - each serving 390 businesses"
3. **Proven Demand:** "These aren't speculative areas - they're established commercial zones with 50 to 1,170 active businesses already operating"
4. **First-Mover Advantage:** "Most of these areas have 1-3 financial services total - early entrants can establish market dominance before competition arrives"

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
FROM `your-project-id.places_insights___id.places`
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

### Actual Results (Top 15 Districts by Rating)

| District | Banks | Avg Rating | Avg Reviews | Excellent % | Accessible |
|----------|-------|------------|-------------|-------------|------------|
| Kecamatan Senen | 91 | 4.24 | 25.4 | 62.6% | 11 |
| Kecamatan Menteng | 145 | 4.23 | 26.8 | 50.3% | 27 |
| Kecamatan Pasar Rebo | 31 | 4.20 | 48.7 | 41.9% | 2 |
| Kecamatan Tanah Abang | 263 | 4.19 | 30.0 | 49.4% | 40 |
| Kecamatan Sawah Besar | 140 | 4.18 | 17.8 | 47.9% | 10 |

### Key Insights

1. **District Quality Range:** Top districts average 4.18-4.24 rating - narrow 0.06 point spread among leaders
2. **Excellence Variation:** Senen leads with 62.6% excellent banks vs Pasar Rebo at 41.9% - 21 point gap
3. **Size vs Quality:** Tanah Abang has 263 banks (largest) but ranks 4th in quality - scale doesn't guarantee excellence
4. **Review Engagement:** Pasar Rebo averages 48.7 reviews despite having only 31 banks - high customer engagement
5. **Accessibility Leaders:** Tanah Abang (40 accessible) and Setiabudi (69 accessible) lead in inclusive infrastructure

### Talking Points

1. **Premium Districts:** "Senen and Menteng lead in quality with 4.23-4.24 average ratings and 50-63% excellent banks"
2. **Market Opportunity:** "Even top districts show room for improvement - best district is only 4.24 vs theoretical 5.0 maximum"
3. **Engagement Matters:** "Smaller districts like Pasar Rebo punch above their weight with 48.7 average reviews - quality drives engagement"
4. **Strategic Targeting:** "Banks can choose: compete in premium districts (Menteng, Senen) or improve service in lower-rated areas"

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
FROM `your-project-id.places_insights___id.places`
WHERE
  ('Jakarta' IN UNNEST(locality_names)
   OR administrative_area_level_1_name LIKE '%Jakarta%')
  AND 'bank' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
```

### Actual Results

| total_banks | saturday_service | sunday_service | early_opening | late_closing | saturday_pct | sunday_pct |
|-------------|------------------|----------------|---------------|--------------|--------------|------------|
| 7,320 | 1,236 | 1,039 | 3,860 | 1,455 | 16.9% | 14.2% |

### Key Insights

1. **Weekend Service Gap:** Only 16.9% open Saturday, 14.2% Sunday - 83% of banks unavailable on weekends
2. **Early Birds:** 52.7% (3,860) open by 8am Monday - majority serve early customers on weekdays
3. **Evening Service Limited:** Only 19.9% (1,455) stay open past 5pm - most close during business hours
4. **Customer Inconvenience:** Working customers (9am-5pm jobs) must take time off for 80% of banks
5. **Differentiation Opportunity:** Weekend/evening service represents major competitive advantage for early adopters

### Talking Points

1. **Massive Weekend Gap:** "83% of Jakarta banks close on Saturday - forcing working customers to choose between banking and their jobs"
2. **Evening Access Limited:** "Only 20% of banks stay open past 5pm - most close before customers finish work"
3. **Competitive Advantage:** "Banks offering weekend/evening hours can capture the 80% of customers underserved by traditional schedules"
4. **ATM Dependency:** "Limited hours drive customers to ATMs for basic services - banks miss relationship-building opportunities"

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
FROM `your-project-id.places_insights___id.places`
WHERE
  ('Jakarta' IN UNNEST(locality_names)
   OR administrative_area_level_1_name LIKE '%Jakarta%')
  AND ('bank' IN UNNEST(types) OR 'atm' IN UNNEST(types))
  AND business_status = 'OPERATIONAL'
```

### Actual Results

| total_locations | credit_cards | debit_cards | nfc_payment | cash_only | nfc_adoption_pct | credit_adoption_pct | debit_adoption_pct |
|-----------------|--------------|-------------|-------------|-----------|------------------|---------------------|-------------------|
| 17,135 | 512 | 527 | 510 | 7 | 3.0% | 3.0% | 3.1% |

### Key Insights

1. **Severe Data Gap:** Only 3% of locations report payment methods - 97% data transparency gap
2. **Digital Payment Scarcity:** 510 locations (3%) report NFC capability out of 17,135 total
3. **Card Acceptance Low:** Credit (512) and debit (527) card reporting equally sparse at ~3%
4. **Cash Dominance Unclear:** Only 7 locations explicitly report cash-only - but lack of data doesn't mean digital acceptance
5. **First-Mover Advantage:** Banks publicizing digital capabilities can differentiate in data-sparse market

### Talking Points

1. **Transparency Opportunity:** "97% of financial locations don't report payment methods - banks that publicize digital capabilities gain immediate visibility advantage"
2. **Digital Payment Gap:** "Only 3% report NFC/contactless payment - massive opportunity for banks to lead digital transformation"
3. **Customer Expectations:** "Modern customers expect contactless payment - but can't find which banks offer it due to data gaps"
4. **Competitive Edge:** "First banks to prominently advertise digital payment capabilities will capture tech-savvy customer segment"

### Strategic Implications

1. **Publicize Digital Capabilities:** Update Google Business profiles with payment methods
2. **Lead Market Education:** Promote NFC/contactless as differentiator
3. **Infrastructure Investment:** Ensure all touchpoints support modern payment methods
4. **Marketing Advantage:** Position as "Jakarta's most digitally advanced bank"

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
CROSS JOIN `your-project-id.places_insights___id.places` p
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
  FROM `your-project-id.places_insights___id.places`,
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
  FROM `your-project-id.places_insights___id.places`
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
  CROSS JOIN `your-project-id.places_insights___id.places` p
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
   - Point size: 15-20
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
