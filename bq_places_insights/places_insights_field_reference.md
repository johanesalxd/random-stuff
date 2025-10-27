# Places Insights Field Reference & Use Cases Guide
## Indonesia Dataset - Complete Reference

**Dataset:** `johanesa-playground-326616.places_insights___id.places`
**Region:** Indonesia (All major cities)
**Last Updated:** October 2025

---

## 📋 Table of Contents

1. [Dataset Overview](#dataset-overview)
2. [Complete Field Reference](#complete-field-reference)
3. [Most Commonly Used Fields](#most-commonly-used-fields)
4. [Top 10 General Use Cases](#top-10-general-use-cases)
5. [Top 10 Banking/Finance Use Cases](#top-10-bankingfinance-use-cases)
6. [Best Practices](#best-practices)
7. [Query Patterns](#query-patterns)

---

## Dataset Overview

### Coverage

The Indonesia Places Insights dataset covers **all major cities** with comprehensive place data:

| City/Area | Place Count | Notes |
|-----------|-------------|-------|
| Greater Jakarta | 820,000+ | East, South, West, North, Central |
| Kabupaten Bekasi | 292,000+ | Greater Jakarta area |
| Surabaya | 264,000+ | East Java's largest city |
| Kota Bekasi | 254,000+ | Greater Jakarta area |
| Depok | 245,000+ | Greater Jakarta area |
| Bandung | 243,000+ | West Java's capital |
| Tangerang | 352,000+ | South & main Tangerang |
| Medan | 158,000+ | North Sumatra's capital |
| Makassar | 151,000+ | South Sulawesi's capital |
| Denpasar | 136,000+ | Bali's capital |
| Semarang | 135,000+ | Central Java's capital |

### Key Characteristics

- **Total Places:** 3+ million operational places
- **Update Frequency:** Regular updates from Google Maps
- **Privacy Protection:** Aggregation threshold (count ≥ 5) required
- **Geographic Precision:** Latitude/longitude coordinates
- **Rich Metadata:** 70+ fields covering location, quality, services, hours

---

## Complete Field Reference

### Location & Geography Fields

| Field Name | Type | Description | Example | Use Cases |
|------------|------|-------------|---------|-----------|
| `point` | GEOGRAPHY | Geographic point (lat/long) | POINT(106.82 -6.19) | Spatial queries, distance calculations |
| `location.latitude` | FLOAT | Latitude coordinate | -6.19 | Mapping, joins |
| `location.longitude` | FLOAT | Longitude coordinate | 106.82 | Mapping, joins |
| `country_code` | STRING | ISO country code | "ID" | Country filtering |
| `administrative_area_level_1_name` | STRING | Province/state name | "Jakarta" | Regional analysis |
| `administrative_area_level_1_id` | STRING | Province Place ID | "ChIJ..." | Geographic joins |
| `administrative_area_level_2_name` | STRING | City/regency name | "Jakarta Selatan" | City-level analysis |
| `administrative_area_level_2_id` | STRING | City Place ID | "ChIJ..." | Geographic joins |
| `administrative_area_level_3_name` | STRING | District name | "Kebayoran Baru" | District analysis |
| `administrative_area_level_3_id` | STRING | District Place ID | "ChIJ..." | Geographic joins |
| `administrative_area_level_4_name` | STRING | Sub-district name | Variable | Fine-grained analysis |
| `administrative_area_level_4_id` | STRING | Sub-district Place ID | "ChIJ..." | Geographic joins |
| `administrative_area_level_5_name` | STRING | Village/kelurahan | Variable | Hyper-local analysis |
| `administrative_area_level_5_id` | STRING | Village Place ID | "ChIJ..." | Geographic joins |
| `administrative_area_level_6_name` | STRING | Neighborhood | Variable | Micro-level analysis |
| `administrative_area_level_6_id` | STRING | Neighborhood Place ID | "ChIJ..." | Geographic joins |
| `administrative_area_level_7_name` | STRING | Sub-neighborhood | Variable | Ultra-fine analysis |
| `administrative_area_level_7_id` | STRING | Sub-neighborhood ID | "ChIJ..." | Geographic joins |
| `locality_names` | ARRAY<STRING> | City/locality names | ["Jakarta", "Jakarta Selatan"] | Multi-locality filtering |
| `locality_ids` | ARRAY<STRING> | Locality Place IDs | ["ChIJ..."] | Geographic joins |
| `postal_code_names` | ARRAY<STRING> | Postal codes | ["12345"] | Postal code analysis |
| `postal_code_ids` | ARRAY<STRING> | Postal code Place IDs | ["ChIJ..."] | Geographic joins |

### Identification Fields

| Field Name | Type | Description | Example | Use Cases |
|------------|------|-------------|---------|-----------|
| `id` | STRING | Unique Google Place ID | "ChIJN1t_tDeuEmsRUsoyG83frY4" | Unique identifier, joins |
| `types` | ARRAY<STRING> | All place types | ["restaurant", "food", "point_of_interest"] | Multi-type filtering |
| `primary_type` | STRING | Primary classification | "restaurant" | Main type filtering |

### Quality & Reputation Fields

| Field Name | Type | Description | Example | Use Cases |
|------------|------|-------------|---------|-----------|
| `rating` | FLOAT | Average rating (1.0-5.0) | 4.5 | Quality benchmarking |
| `user_rating_count` | INTEGER | Number of reviews | 234 | Popularity metric |
| `business_status` | STRING | Operational status | "OPERATIONAL" | Filter active places |
| `price_level` | STRING | Price category | "PRICE_LEVEL_MODERATE" | Price analysis |

**Price Level Values:**
- `PRICE_LEVEL_FREE`
- `PRICE_LEVEL_INEXPENSIVE`
- `PRICE_LEVEL_MODERATE`
- `PRICE_LEVEL_EXPENSIVE`
- `PRICE_LEVEL_VERY_EXPENSIVE`

**Business Status Values:**
- `OPERATIONAL`
- `CLOSED_TEMPORARILY`
- `CLOSED_PERMANENTLY`

### Service & Amenity Fields

| Field Name | Type | Description | Example | Use Cases |
|------------|------|-------------|---------|-----------|
| `takeout` | BOOLEAN | Offers takeout | true | Service analysis |
| `delivery` | BOOLEAN | Offers delivery | true | Service analysis |
| `dine_in` | BOOLEAN | Offers dine-in | true | Service analysis |
| `curbside_pickup` | BOOLEAN | Offers curbside pickup | false | Service analysis |
| `reservable` | BOOLEAN | Accepts reservations | true | Service analysis |
| `serves_breakfast` | BOOLEAN | Serves breakfast | true | Meal service analysis |
| `serves_lunch` | BOOLEAN | Serves lunch | true | Meal service analysis |
| `serves_dinner` | BOOLEAN | Serves dinner | true | Meal service analysis |
| `serves_beer` | BOOLEAN | Serves beer | true | Beverage analysis |
| `serves_wine` | BOOLEAN | Serves wine | true | Beverage analysis |
| `serves_brunch` | BOOLEAN | Serves brunch | false | Meal service analysis |
| `serves_vegetarian_food` | BOOLEAN | Vegetarian options | true | Dietary analysis |
| `outdoor_seating` | BOOLEAN | Has outdoor seating | true | Amenity analysis |
| `live_music` | BOOLEAN | Offers live music | false | Entertainment analysis |
| `menu_for_children` | BOOLEAN | Children's menu | true | Family-friendly analysis |
| `serves_cocktails` | BOOLEAN | Serves cocktails | true | Beverage analysis |
| `serves_dessert` | BOOLEAN | Serves dessert | true | Menu analysis |
| `serves_coffee` | BOOLEAN | Serves coffee | true | Beverage analysis |
| `good_for_children` | BOOLEAN | Child-friendly | true | Family analysis |
| `allows_dogs` | BOOLEAN | Pet-friendly | false | Pet policy analysis |
| `restroom` | BOOLEAN | Has restroom | true | Amenity analysis |
| `good_for_groups` | BOOLEAN | Group-friendly | true | Capacity analysis |
| `good_for_watching_sports` | BOOLEAN | Sports viewing | false | Entertainment analysis |

### Payment & Accessibility Fields

| Field Name | Type | Description | Example | Use Cases |
|------------|------|-------------|---------|-----------|
| `accepts_credit_cards` | BOOLEAN | Accepts credit cards | true | Payment analysis |
| `accepts_debit_cards` | BOOLEAN | Accepts debit cards | true | Payment analysis |
| `accepts_cash_only` | BOOLEAN | Cash only | false | Payment analysis |
| `accepts_nfc` | BOOLEAN | NFC/contactless payment | true | Digital payment analysis |
| `wheelchair_accessible_entrance` | BOOLEAN | Wheelchair accessible | true | Accessibility analysis |
| `wheelchair_accessible_restroom` | BOOLEAN | Accessible restroom | false | Accessibility analysis |
| `wheelchair_accessible_seating` | BOOLEAN | Accessible seating | false | Accessibility analysis |
| `wheelchair_accessible_parking` | BOOLEAN | Accessible parking | false | Accessibility analysis |

### Parking Fields

| Field Name | Type | Description | Example | Use Cases |
|------------|------|-------------|---------|-----------|
| `free_parking_lot` | BOOLEAN | Free parking lot | false | Parking analysis |
| `paid_parking_lot` | BOOLEAN | Paid parking lot | true | Parking analysis |
| `free_street_parking` | BOOLEAN | Free street parking | false | Parking analysis |
| `paid_street_parking` | BOOLEAN | Paid street parking | true | Parking analysis |
| `valet_parking` | BOOLEAN | Valet parking | false | Parking analysis |
| `free_garage_parking` | BOOLEAN | Free garage parking | false | Parking analysis |
| `paid_garage_parking` | BOOLEAN | Paid garage parking | true | Parking analysis |

### Operating Hours Fields

| Field Name | Type | Description | Example | Use Cases |
|------------|------|-------------|---------|-----------|
| `regular_opening_hours` | RECORD | Regular hours by day | See structure below | Hours analysis |
| `regular_opening_hours_happy_hour` | RECORD | Happy hour times | See structure below | Special hours |
| `regular_opening_hours_drive_through` | RECORD | Drive-through hours | See structure below | Service hours |
| `regular_opening_hours_delivery` | RECORD | Delivery hours | See structure below | Service hours |
| `regular_opening_hours_takeout` | RECORD | Takeout hours | See structure below | Service hours |
| `regular_opening_hours_kitchen` | RECORD | Kitchen hours | See structure below | Service hours |
| `regular_opening_hours_breakfast` | RECORD | Breakfast hours | See structure below | Meal hours |
| `regular_opening_hours_lunch` | RECORD | Lunch hours | See structure below | Meal hours |
| `regular_opening_hours_dinner` | RECORD | Dinner hours | See structure below | Meal hours |
| `regular_opening_hours_brunch` | RECORD | Brunch hours | See structure below | Meal hours |
| `regular_opening_hours_pickup` | RECORD | Pickup hours | See structure below | Service hours |
| `regular_opening_hours_access` | RECORD | Access hours | See structure below | Service hours |
| `regular_opening_hours_senior_hours` | RECORD | Senior hours | See structure below | Special hours |
| `regular_opening_hours_online_service_hours` | RECORD | Online service hours | See structure below | Service hours |

**Opening Hours Structure:**
```
{
  monday: [{start_time: TIME, end_time: TIME}],
  tuesday: [{start_time: TIME, end_time: TIME}],
  wednesday: [{start_time: TIME, end_time: TIME}],
  thursday: [{start_time: TIME, end_time: TIME}],
  friday: [{start_time: TIME, end_time: TIME}],
  saturday: [{start_time: TIME, end_time: TIME}],
  sunday: [{start_time: TIME, end_time: TIME}]
}
```

### EV Charging Fields

| Field Name | Type | Description | Example | Use Cases |
|------------|------|-------------|---------|-----------|
| `ev_charge_options` | RECORD | EV charging info | See structure below | EV infrastructure |
| `ev_charge_options.connector_count` | INTEGER | Total connectors | 4 | Capacity analysis |
| `ev_charge_options.connector_aggregation` | ARRAY<RECORD> | Connector details | See below | Detailed EV analysis |

**EV Connector Aggregation Structure:**
```
[{
  type: STRING,           // e.g., "EV_CONNECTOR_TYPE_TESLA"
  max_charge_rate_kw: FLOAT,  // e.g., 150.0
  count: INTEGER          // e.g., 2
}]
```

---

## Most Commonly Used Fields

### Quick Reference - Top 30 Fields (80% of Use Cases)

| Field | Type | Primary Use | Query Frequency |
|-------|------|-------------|-----------------|
| `point` | GEOGRAPHY | 🗺️ Mapping, spatial queries | ⭐⭐⭐⭐⭐ |
| `location.latitude` | FLOAT | 📍 Coordinates | ⭐⭐⭐⭐⭐ |
| `location.longitude` | FLOAT | 📍 Coordinates | ⭐⭐⭐⭐⭐ |
| `id` | STRING | 🔑 Unique identifier | ⭐⭐⭐⭐⭐ |
| `types` | ARRAY<STRING> | 🏷️ Multi-type filtering | ⭐⭐⭐⭐⭐ |
| `primary_type` | STRING | 🏷️ Main classification | ⭐⭐⭐⭐⭐ |
| `business_status` | STRING | ✅ Filter operational | ⭐⭐⭐⭐⭐ |
| `rating` | FLOAT | ⭐ Quality metric | ⭐⭐⭐⭐⭐ |
| `user_rating_count` | INTEGER | 📊 Popularity | ⭐⭐⭐⭐ |
| `locality_names` | ARRAY<STRING> | 🏙️ City filtering | ⭐⭐⭐⭐⭐ |
| `postal_code_names` | ARRAY<STRING> | 📮 Postal analysis | ⭐⭐⭐⭐ |
| `administrative_area_level_1_name` | STRING | 🗺️ Province | ⭐⭐⭐⭐ |
| `administrative_area_level_2_name` | STRING | 🏙️ City/regency | ⭐⭐⭐⭐ |
| `administrative_area_level_3_name` | STRING | 📍 District | ⭐⭐⭐⭐ |
| `price_level` | STRING | 💰 Price analysis | ⭐⭐⭐ |
| `regular_opening_hours` | RECORD | 🕐 Hours analysis | ⭐⭐⭐⭐ |
| `wheelchair_accessible_entrance` | BOOLEAN | ♿ Accessibility | ⭐⭐⭐ |
| `accepts_credit_cards` | BOOLEAN | 💳 Payment methods | ⭐⭐⭐ |
| `accepts_nfc` | BOOLEAN | 📱 Digital payment | ⭐⭐⭐ |
| `delivery` | BOOLEAN | 🚚 Service options | ⭐⭐⭐ |
| `takeout` | BOOLEAN | 🥡 Service options | ⭐⭐⭐ |
| `dine_in` | BOOLEAN | 🍽️ Service options | ⭐⭐⭐ |
| `outdoor_seating` | BOOLEAN | 🌳 Amenities | ⭐⭐ |
| `good_for_children` | BOOLEAN | 👶 Family-friendly | ⭐⭐ |
| `good_for_groups` | BOOLEAN | 👥 Group capacity | ⭐⭐ |
| `serves_vegetarian_food` | BOOLEAN | 🥗 Dietary options | ⭐⭐ |
| `free_parking_lot` | BOOLEAN | 🅿️ Parking | ⭐⭐ |
| `paid_parking_lot` | BOOLEAN | 🅿️ Parking | ⭐⭐ |
| `reservable` | BOOLEAN | 📅 Reservations | ⭐⭐ |
| `ev_charge_options` | RECORD | 🔌 EV infrastructure | ⭐ |

---

## Top 10 General Use Cases

### Use Case 1: Geographic Density Mapping

**Business Question:** *Where are places concentrated across Indonesian cities?*

**Query:**
```sql
-- Geographic density heatmap for any city
SELECT
  geo_txt,
  ST_GEOGFROMTEXT(geo_txt) AS geo,
  total_count,
  avg_rating
FROM (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS total_count,
    ROUND(AVG(rating), 2) AS avg_rating
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    'Surabaya' IN UNNEST(locality_names)  -- Change city as needed
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
)
ORDER BY total_count DESC
LIMIT 100;
```

**Visualization:**
1. Run query in BigQuery Studio
2. Click "Visualization" tab
3. Set Data Column to `total_count`
4. Use "Viridis" color scheme

**Expected Insights:**
- Identify commercial centers
- Find underserved areas
- Understand city structure

**Variations:**
- Change grid size: `0.005` (finer) or `0.02` (coarser)
- Filter by type: Add `AND 'restaurant' IN UNNEST(types)`
- Multiple cities: Use `IN ('Jakarta', 'Surabaya', 'Bandung')`

---

### Use Case 2: Quality Benchmarking

**Business Question:** *How do places perform on quality metrics?*

**Query:**
```sql
-- Rating distribution analysis
SELECT WITH AGGREGATION_THRESHOLD
  CASE
    WHEN rating >= 4.5 THEN 'Excellent (4.5+)'
    WHEN rating >= 4.0 THEN 'Good (4.0-4.5)'
    WHEN rating >= 3.5 THEN 'Average (3.5-4.0)'
    ELSE 'Below Average (<3.5)'
  END AS rating_category,
  COUNT(*) AS place_count,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews,
  ROUND(AVG(rating), 2) AS avg_rating_in_category
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Bandung' IN UNNEST(locality_names)
  AND 'restaurant' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND rating IS NOT NULL
GROUP BY rating_category
ORDER BY rating_category DESC;
```

**Expected Results:**
| rating_category | place_count | avg_reviews | avg_rating_in_category |
|-----------------|-------------|-------------|------------------------|
| Excellent (4.5+) | 5,234 | 45.2 | 4.7 |
| Good (4.0-4.5) | 3,421 | 28.3 | 4.2 |
| Average (3.5-4.0) | 1,892 | 18.7 | 3.7 |
| Below Average (<3.5) | 987 | 12.1 | 3.1 |

**Insights:**
- Quality distribution across market
- Review engagement correlation
- Competitive benchmarks

---

### Use Case 3: Competitive Landscape Analysis

**Business Question:** *How many competitors exist in each area?*

**Query:**
```sql
-- Competitor count by district
SELECT WITH AGGREGATION_THRESHOLD
  administrative_area_level_3_name AS district,
  COUNT(*) AS total_places,
  COUNTIF(rating >= 4.5) AS excellent_places,
  ROUND(AVG(rating), 2) AS avg_rating,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Medan' IN UNNEST(locality_names)
  AND 'cafe' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND administrative_area_level_3_name IS NOT NULL
GROUP BY district
HAVING total_places >= 5
ORDER BY total_places DESC
LIMIT 20;
```

**Insights:**
- Identify saturated markets
- Find underserved districts
- Competitive intensity mapping

---

### Use Case 4: Operating Hours Analysis

**Business Question:** *When are places open for business?*

**Query:**
```sql
-- Places open during specific hours
SELECT WITH AGGREGATION_THRESHOLD
  COUNT(*) AS total_places,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.monday) AS hours
    WHERE hours.start_time <= TIME '09:00:00'
    AND hours.end_time >= TIME '17:00:00'
  )) AS open_business_hours,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.saturday) AS hours
    WHERE hours.start_time IS NOT NULL
  )) AS saturday_service,
  COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.sunday) AS hours
    WHERE hours.start_time IS NOT NULL
  )) AS sunday_service,
  ROUND(COUNTIF(EXISTS(
    SELECT 1 FROM UNNEST(regular_opening_hours.saturday) AS hours
    WHERE hours.start_time IS NOT NULL
  )) / COUNT(*) * 100, 1) AS saturday_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Denpasar' IN UNNEST(locality_names)
  AND 'restaurant' IN UNNEST(types)
  AND business_status = 'OPERATIONAL';
```

**Insights:**
- Weekend service availability
- Business hours patterns
- Service gap identification

---

### Use Case 5: Accessibility Assessment

**Business Question:** *How accessible are places for all customers?*

**Query:**
```sql
-- Accessibility features analysis
SELECT WITH AGGREGATION_THRESHOLD
  primary_type,
  COUNT(*) AS total_count,
  COUNTIF(wheelchair_accessible_entrance = true) AS accessible_entrance,
  COUNTIF(wheelchair_accessible_parking = true) AS accessible_parking,
  COUNTIF(wheelchair_accessible_restroom = true) AS accessible_restroom,
  ROUND(COUNTIF(wheelchair_accessible_entrance = true) / COUNT(*) * 100, 1) AS entrance_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Makassar' IN UNNEST(locality_names)
  AND business_status = 'OPERATIONAL'
  AND primary_type IS NOT NULL
GROUP BY primary_type
HAVING total_count >= 10
ORDER BY total_count DESC
LIMIT 15;
```

**Insights:**
- Accessibility compliance rates
- Industry-specific patterns
- Improvement opportunities

---

### Use Case 6: Multi-Location Comparison

**Business Question:** *How do different cities compare?*

**Query:**
```sql
-- Compare cities across Indonesia
WITH city_stats AS (
  SELECT WITH AGGREGATION_THRESHOLD
    locality,
    COUNT(*) AS total_places,
    ROUND(AVG(rating), 2) AS avg_rating,
    ROUND(AVG(user_rating_count), 1) AS avg_reviews,
    COUNTIF(rating >= 4.5) AS excellent_count
  FROM `johanesa-playground-326616.places_insights___id.places`,
  UNNEST(locality_names) AS locality
  WHERE
    locality IN ('Jakarta Selatan', 'Surabaya', 'Bandung', 'Medan', 'Denpasar')
    AND 'restaurant' IN UNNEST(types)
    AND business_status = 'OPERATIONAL'
  GROUP BY locality
)
SELECT
  locality,
  total_places,
  avg_rating,
  avg_reviews,
  ROUND(excellent_count / total_places * 100, 1) AS excellent_pct
FROM city_stats
ORDER BY total_places DESC;
```

**Insights:**
- Market size comparison
- Quality standards by city
- Regional preferences

---

### Use Case 7: Price Level Distribution

**Business Question:** *What's the pricing landscape?*

**Query:**
```sql
-- Price level analysis
SELECT WITH AGGREGATION_THRESHOLD
  price_level,
  COUNT(*) AS place_count,
  ROUND(AVG(rating), 2) AS avg_rating,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Semarang' IN UNNEST(locality_names)
  AND 'restaurant' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND price_level IS NOT NULL
GROUP BY price_level
ORDER BY
  CASE price_level
    WHEN 'PRICE_LEVEL_FREE' THEN 1
    WHEN 'PRICE_LEVEL_INEXPENSIVE' THEN 2
    WHEN 'PRICE_LEVEL_MODERATE' THEN 3
    WHEN 'PRICE_LEVEL_EXPENSIVE' THEN 4
    WHEN 'PRICE_LEVEL_VERY_EXPENSIVE' THEN 5
  END;
```

**Insights:**
- Price distribution
- Quality-price correlation
- Market positioning

---

### Use Case 8: Place Type Distribution

**Business Question:** *What types of businesses exist in an area?*

**Query:**
```sql
-- Top place types in a city
SELECT WITH AGGREGATION_THRESHOLD
  primary_type,
  COUNT(*) AS count,
  ROUND(AVG(rating), 2) AS avg_rating,
  COUNTIF(rating >= 4.5) AS excellent_count
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Tangerang Selatan' IN UNNEST(locality_names)
  AND business_status = 'OPERATIONAL'
  AND primary_type IS NOT NULL
GROUP BY primary_type
ORDER BY count DESC
LIMIT 20;
```

**Insights:**
- Business composition
- Market opportunities
- Industry trends

---

### Use Case 9: Service Feature Analysis

**Business Question:** *What services do places offer?*

**Query:**
```sql
-- Service availability analysis
SELECT WITH AGGREGATION_THRESHOLD
  COUNT(*) AS total_restaurants,
  COUNTIF(delivery = true) AS offers_delivery,
  COUNTIF(takeout = true) AS offers_takeout,
  COUNTIF(dine_in = true) AS offers_dine_in,
  COUNTIF(outdoor_seating = true) AS has_outdoor_seating,
  COUNTIF(reservable = true) AS accepts_reservations,
  ROUND(COUNTIF(delivery = true) / COUNT(*) * 100, 1) AS delivery_pct,
  ROUND(COUNTIF(takeout = true) / COUNT(*) * 100, 1) AS takeout_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Depok' IN UNNEST(locality_names)
  AND 'restaurant' IN UNNEST(types)
  AND business_status = 'OPERATIONAL';
```

**Insights:**
- Service adoption rates
- Customer convenience options
- Competitive features

---

### Use Case 10: Regional Performance Comparison

**Business Question:** *How do different districts perform within a city?*

**Query:**
```sql
-- District-level performance analysis
SELECT WITH AGGREGATION_THRESHOLD
  administrative_area_level_3_name AS district,
  COUNT(*) AS place_count,
  ROUND(AVG(rating), 2) AS avg_rating,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews,
  COUNTIF(price_level = 'PRICE_LEVEL_EXPENSIVE'
       OR price_level = 'PRICE_LEVEL_VERY_EXPENSIVE') AS premium_count,
  ROUND(COUNTIF(rating >= 4.5) / COUNT(*) * 100, 1) AS excellent_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  administrative_area_level_2_name = 'Jakarta Selatan'
  AND 'restaurant' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND administrative_area_level_3_name IS NOT NULL
  AND rating IS NOT NULL
GROUP BY district
HAVING place_count >= 10
ORDER BY avg_rating DESC
LIMIT 15;
```

**Insights:**
- Premium vs budget areas
- Quality by neighborhood
- Strategic positioning

---

## Top 10 Banking/Finance Use Cases

### Use Case 1: Branch Network Coverage Analysis

**Business Question:** *Where are banks and ATMs distributed across the city?*

**Query:**
```sql
-- Banking network density map
SELECT
  geo_txt,
  ST_GEOGFROMTEXT(geo_txt) AS geo,
  total_count,
  bank_count,
  atm_count,
  finance_count
FROM (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS total_count,
    COUNTIF('bank' IN UNNEST(types)) AS bank_count,
    COUNTIF('atm' IN UNNEST(types)) AS atm_count,
    COUNTIF('finance' IN UNNEST(types)) AS finance_count
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    'Surabaya' IN UNNEST(locality_names)
    AND (
      'bank' IN UNNEST(types)
      OR 'atm' IN UNNEST(types)
      OR 'finance' IN UNNEST(types)
    )
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
)
ORDER BY total_count DESC
LIMIT 100;
```

**Visualization:**
- BigQuery Studio heatmap
- Data Column: `total_count`
- Color: Viridis (dark = high density)

**Insights:**
- Network coverage gaps
- Competitive saturation
- Expansion opportunities

---

### Use Case 2: ATM Accessibility Gap Analysis

**Business Question:** *Where are underserved areas with high commercial activity but few ATMs?*

**Query:**
```sql
-- White space analysis for ATM placement
WITH commercial_activity AS (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS total_businesses,
    COUNTIF('shopping_mall' IN UNNEST(types)
         OR 'store' IN UNNEST(types)
         OR 'restaurant' IN UNNEST(types)) AS commercial_count,
    COUNTIF('atm' IN UNNEST(types)) AS atm_count
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    'Bandung' IN UNNEST(locality_names)
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
  HAVING commercial_count > 0
)
SELECT
  geo_txt,
  ST_GEOGFROMTEXT(geo_txt) AS geo,
  commercial_count,
  atm_count,
  ROUND(commercial_count / NULLIF(atm_count, 0), 2) AS opportunity_score
FROM commercial_activity
WHERE atm_count < 5
  AND commercial_count > 50
ORDER BY opportunity_score DESC
LIMIT 20;
```

**Visualization:**
- Heatmap with `opportunity_score` as data column
- Red color scheme (hotter = better opportunity)

**Insights:**
- High-traffic areas lacking ATMs
- Expansion priority zones
- Customer convenience gaps

---

### Use Case 3: Service Quality Benchmarking

**Business Question:** *How do banks perform on customer satisfaction?*

**Query:**
```sql
-- Banking service quality analysis
SELECT WITH AGGREGATION_THRESHOLD
  CASE
    WHEN rating >= 4.5 THEN 'Excellent (4.5+)'
    WHEN rating >= 4.0 THEN 'Good (4.0-4.5)'
    WHEN rating >= 3.5 THEN 'Average (3.5-4.0)'
    ELSE 'Below Average (<3.5)'
  END AS rating_category,
  COUNT(*) AS bank_count,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews,
  COUNTIF(wheelchair_accessible_entrance = true) AS accessible_count,
  ROUND(COUNTIF(wheelchair_accessible_entrance = true) / COUNT(*) * 100, 1) AS accessibility_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
    'Jakarta Selatan' IN UNNEST(locality_names)
  AND 'bank' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND rating IS NOT NULL
GROUP BY rating_category
ORDER BY rating_category DESC;
```

**Insights:**
- Quality distribution benchmarks
- Review engagement patterns
- Accessibility compliance gaps

---

### Use Case 4: Operating Hours Optimization

**Business Question:** *When are banks open vs customer needs?*

**Query:**
```sql
-- Banking hours analysis
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
  )) / COUNT(*) * 100, 1) AS saturday_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Medan' IN UNNEST(locality_names)
  AND 'bank' IN UNNEST(types)
  AND business_status = 'OPERATIONAL';
```

**Insights:**
- Weekend service availability
- Extended hours adoption
- Customer convenience gaps

---

### Use Case 5: Payment Method Adoption

**Business Question:** *What payment methods do financial services accept?*

**Query:**
```sql
-- Payment method analysis
SELECT WITH AGGREGATION_THRESHOLD
  COUNT(*) AS total_locations,
  COUNTIF(accepts_credit_cards = true) AS credit_cards,
  COUNTIF(accepts_debit_cards = true) AS debit_cards,
  COUNTIF(accepts_nfc = true) AS nfc_payment,
  COUNTIF(accepts_cash_only = true) AS cash_only,
  ROUND(COUNTIF(accepts_nfc = true) / COUNT(*) * 100, 1) AS nfc_adoption_pct,
  ROUND(COUNTIF(accepts_credit_cards = true) / COUNT(*) * 100, 1) AS credit_adoption_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Denpasar' IN UNNEST(locality_names)
  AND ('bank' IN UNNEST(types) OR 'atm' IN UNNEST(types))
  AND business_status = 'OPERATIONAL';
```

**Insights:**
- Digital payment adoption
- Cash dependency levels
- Technology modernization gaps

---

### Use Case 6: Multi-City Banking Comparison

**Business Question:** *How does banking infrastructure vary across Indonesian cities?*

**Query:**
```sql
-- Compare banking across major cities
WITH city_banking AS (
  SELECT WITH AGGREGATION_THRESHOLD
    locality,
    COUNT(*) AS total_financial_services,
    COUNTIF('bank' IN UNNEST(types)) AS bank_count,
    COUNTIF('atm' IN UNNEST(types)) AS atm_count,
    ROUND(AVG(rating), 2) AS avg_rating,
    COUNTIF(rating >= 4.5) AS excellent_count
  FROM `johanesa-playground-326616.places_insights___id.places`,
  UNNEST(locality_names) AS locality
  WHERE
    locality IN ('Jakarta Selatan', 'Surabaya', 'Bandung', 'Medan', 'Makassar')
    AND ('bank' IN UNNEST(types) OR 'atm' IN UNNEST(types))
    AND business_status = 'OPERATIONAL'
  GROUP BY locality
)
SELECT
  locality,
  total_financial_services,
  bank_count,
  atm_count,
  avg_rating,
  ROUND(excellent_count / total_financial_services * 100, 1) AS excellent_pct,
  ROUND(atm_count / NULLIF(bank_count, 0), 2) AS atm_per_bank_ratio
FROM city_banking
ORDER BY total_financial_services DESC;
```

**Insights:**
- Market size by city
- ATM-to-branch ratios
- Quality standards variation

---

### Use Case 7: Accessibility Compliance Analysis

**Business Question:** *How accessible are banking services?*

**Query:**
```sql
-- Banking accessibility assessment
SELECT WITH AGGREGATION_THRESHOLD
  administrative_area_level_3_name AS district,
  COUNT(*) AS bank_count,
  COUNTIF(wheelchair_accessible_entrance = true) AS accessible_entrance,
  COUNTIF(wheelchair_accessible_parking = true) AS accessible_parking,
  ROUND(COUNTIF(wheelchair_accessible_entrance = true) / COUNT(*) * 100, 1) AS entrance_pct,
  ROUND(AVG(rating), 2) AS avg_rating
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Surabaya' IN UNNEST(locality_names)
  AND 'bank' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND administrative_area_level_3_name IS NOT NULL
GROUP BY district
HAVING bank_count >= 5
ORDER BY entrance_pct DESC
LIMIT 15;
```

**Insights:**
- Compliance rates by district
- Accessibility leaders
- Improvement priorities

---

### Use Case 8: Competitive Positioning by Postal Code

**Business Question:** *What's the competitive landscape in each postal code?*

**Query:**
```sql
-- Market share analysis by postal code
SELECT WITH AGGREGATION_THRESHOLD
  postal_code,
  COUNT(*) AS total_financial_services,
  COUNTIF('bank' IN UNNEST(types)) AS banks,
  COUNTIF('atm' IN UNNEST(types)) AS atms,
  COUNTIF('finance' IN UNNEST(types)) AS finance_companies,
  ROUND(AVG(rating), 2) AS avg_rating,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews
FROM `johanesa-playground-326616.places_insights___id.places`,
UNNEST(postal_code_names) AS postal_code
WHERE
  'Semarang' IN UNNEST(locality_names)
  AND ('bank' IN UNNEST(types) OR 'atm' IN UNNEST(types) OR 'finance' IN UNNEST(types))
  AND business_status = 'OPERATIONAL'
GROUP BY postal_code
HAVING total_financial_services >= 5
ORDER BY total_financial_services DESC
LIMIT 20;
```

**Insights:**
- Postal code saturation levels
- Underserved areas
- Market share opportunities

---

### Use Case 9: Customer Experience Metrics

**Business Question:** *How do customers rate their banking experience?*

**Query:**
```sql
-- Customer satisfaction analysis
SELECT WITH AGGREGATION_THRESHOLD
  primary_type,
  COUNT(*) AS location_count,
  ROUND(AVG(rating), 2) AS avg_rating,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews,
  COUNTIF(rating >= 4.5) AS excellent_count,
  COUNTIF(rating < 3.5) AS poor_count,
  ROUND(COUNTIF(rating >= 4.5) / COUNT(*) * 100, 1) AS excellent_pct,
  ROUND(COUNTIF(rating < 3.5) / COUNT(*) * 100, 1) AS poor_pct
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'Tangerang Selatan' IN UNNEST(locality_names)
  AND ('bank' IN UNNEST(types) OR 'atm' IN UNNEST(types) OR 'finance' IN UNNEST(types))
  AND business_status = 'OPERATIONAL'
  AND rating IS NOT NULL
GROUP BY primary_type
ORDER BY location_count DESC;
```

**Insights:**
- Service type performance
- Customer satisfaction trends
- Problem area identification

---

### Use Case 10: White Space for Branch Expansion

**Business Question:** *Where should we open new branches?*

**Query:**
```sql
-- Strategic expansion opportunities
WITH commercial_density AS (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS total_businesses,
    COUNTIF('shopping_mall' IN UNNEST(types)
         OR 'store' IN UNNEST(types)
         OR 'restaurant' IN UNNEST(types)) AS commercial_count,
    COUNTIF('bank' IN UNNEST(types)) AS bank_count,
    COUNTIF('atm' IN UNNEST(types)) AS atm_count
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    'Makassar' IN UNNEST(locality_names)
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
  HAVING commercial_count > 0
)
SELECT
  geo_txt,
  ST_GEOGFROMTEXT(geo_txt) AS geo,
  commercial_count,
  bank_count,
  atm_count,
  ROUND(commercial_count / NULLIF(bank_count, 0), 2) AS opportunity_score,
  CASE
    WHEN bank_count = 0 THEN 'No Banks'
    WHEN bank_count < 3 THEN 'Low Competition'
    WHEN bank_count < 10 THEN 'Moderate Competition'
    ELSE 'High Competition'
  END AS competition_level
FROM commercial_density
WHERE commercial_count > 100
  AND bank_count < 10
ORDER BY opportunity_score DESC
LIMIT 20;
```

**Visualization:**
- Heatmap with `opportunity_score`
- Filter by `competition_level`

**Insights:**
- Prioritized expansion targets
- Competition intensity
- Market potential quantification

---

## Best Practices

### Query Optimization

**1. Always Use Aggregation Threshold**
```sql
SELECT WITH AGGREGATION_THRESHOLD
  -- Your aggregated query
```
- Required for privacy protection
- Results only returned if count ≥ 5
- Prevents individual place identification

**2. Filter Early and Often**
```sql
WHERE
  business_status = 'OPERATIONAL'  -- Filter closed places
  AND locality_names IS NOT NULL   -- Remove nulls early
  AND 'restaurant' IN UNNEST(types)  -- Type filtering
```

**3. Use Appropriate Grid Sizes**
- **0.005 degrees** (~550m): Fine-grained urban analysis
- **0.01 degrees** (~1.1km): Standard city analysis (recommended)
- **0.02 degrees** (~2.2km): Regional overview
- **0.05 degrees** (~5.5km): Province-level analysis

**4. Optimize Geographic Queries**
```sql
-- Good: Use ST_SNAPTOGRID for aggregation
ST_ASTEXT(ST_SNAPTOGRID(point, 0.01))

-- Good: Use ST_DWITHIN for proximity
ST_DWITHIN(point1, point2, 500)  -- 500 meters

-- Avoid: Complex geographic calculations in WHERE
```

**5. Handle NULL Values**
```sql
-- Always check for NULL in critical fields
WHERE rating IS NOT NULL
  AND administrative_area_level_3_name IS NOT NULL

-- Use NULLIF for division
ROUND(count1 / NULLIF(count2, 0), 2)
```

### Common Patterns

**Pattern 1: Geographic Density**
```sql
SELECT WITH AGGREGATION_THRESHOLD
  ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
  COUNT(*) AS count
FROM table
WHERE filters
GROUP BY geo_txt
```

**Pattern 2: Multi-City Comparison**
```sql
WITH city_stats AS (
  SELECT WITH AGGREGATION_THRESHOLD
    locality,
    COUNT(*) AS count,
    AVG(metric) AS avg_metric
  FROM table, UNNEST(locality_names) AS locality
  WHERE locality IN ('City1', 'City2', 'City3')
  GROUP BY locality
)
SELECT * FROM city_stats
```

**Pattern 3: Quality Distribution**
```sql
SELECT WITH AGGREGATION_THRESHOLD
  CASE
    WHEN rating >= 4.5 THEN 'Excellent'
    WHEN rating >= 4.0 THEN 'Good'
    ELSE 'Average'
  END AS category,
  COUNT(*) AS count
FROM table
WHERE rating IS NOT NULL
GROUP BY category
```

**Pattern 4: Service Feature Analysis**
```sql
SELECT WITH AGGREGATION_THRESHOLD
  COUNT(*) AS total,
  COUNTIF(feature = true) AS has_feature,
  ROUND(COUNTIF(feature = true) / COUNT(*) * 100, 1) AS pct
FROM table
WHERE filters
```

**Pattern 5: Operating Hours Check**
```sql
COUNTIF(EXISTS(
  SELECT 1 FROM UNNEST(regular_opening_hours.monday) AS hours
  WHERE hours.start_time <= TIME '09:00:00'
  AND hours.end_time >= TIME '17:00:00'
)) AS open_during_hours
```

### Data Quality Considerations

**1. Missing Data**
- Not all fields populated for all places
- Accessibility fields often sparse (~10% coverage)
- Price level varies by place type
- Operating hours may be incomplete

**2. Data Freshness**
- Regular updates from Google Maps
- Business status may lag real-world changes
- Ratings and reviews update continuously

**3. Aggregation Threshold**
- Minimum count of 5 required
- May hide small-scale patterns
- Adjust grid size if no results

**4. Type Classification**
- Places can have multiple types
- Use `types` array for comprehensive filtering
- `primary_type` for main classification

### Visualization Best Practices

**BigQuery Studio Heatmaps:**
1. Use geography column named `geo`
2. Choose appropriate data column
3. Select color scheme based on message:
   - **Viridis**: Density (dark = high)
   - **Red-Yellow-Green**: Quality (green = good)
   - **Red**: Intensity/opportunity (red = hot)
4. Adjust circle radius (15-20 pixels typical)
5. Set opacity (70-80% for overlapping circles)

**Looker Studio Dashboards:**
1. Use custom queries for flexibility
2. Create filters for interactivity
3. Combine maps with tables/charts
4. Add scorecards for key metrics

### Common Pitfalls to Avoid

❌ **Don't:**
- Query without `WITH AGGREGATION_THRESHOLD`
- Assume all fields are populated
- Use overly fine grid sizes (< 0.005)
- Ignore NULL values in calculations
- Filter after aggregation when possible before

✅ **Do:**
- Always use aggregation threshold
- Check for NULL values
- Use appropriate grid sizes
- Filter early in WHERE clause
- Test queries with LIMIT first

---

## Query Patterns

### Template: Basic Density Map
```sql
SELECT
  geo_txt,
  ST_GEOGFROMTEXT(geo_txt) AS geo,
  count,
  avg_metric
FROM (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS count,
    AVG(metric) AS avg_metric
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    'CITY_NAME' IN UNNEST(locality_names)
    AND 'TYPE' IN UNNEST(types)
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
)
ORDER BY count DESC
LIMIT 100;
```

### Template: Quality Analysis
```sql
SELECT WITH AGGREGATION_THRESHOLD
  CASE
    WHEN rating >= 4.5 THEN 'Excellent (4.5+)'
    WHEN rating >= 4.0 THEN 'Good (4.0-4.5)'
    WHEN rating >= 3.5 THEN 'Average (3.5-4.0)'
    ELSE 'Below Average (<3.5)'
  END AS rating_category,
  COUNT(*) AS count,
  ROUND(AVG(user_rating_count), 1) AS avg_reviews
FROM `johanesa-playground-326616.places_insights___id.places`
WHERE
  'CITY_NAME' IN UNNEST(locality_names)
  AND 'TYPE' IN UNNEST(types)
  AND business_status = 'OPERATIONAL'
  AND rating IS NOT NULL
GROUP BY rating_category
ORDER BY rating_category DESC;
```

### Template: White Space Analysis
```sql
WITH commercial_activity AS (
  SELECT WITH AGGREGATION_THRESHOLD
    ST_ASTEXT(ST_SNAPTOGRID(point, 0.01)) AS geo_txt,
    COUNT(*) AS total_businesses,
    COUNTIF('COMMERCIAL_TYPE' IN UNNEST(types)) AS commercial_count,
    COUNTIF('TARGET_TYPE' IN UNNEST(types)) AS target_count
  FROM `johanesa-playground-326616.places_insights___id.places`
  WHERE
    'CITY_NAME' IN UNNEST(locality_names)
    AND business_status = 'OPERATIONAL'
  GROUP BY geo_txt
  HAVING commercial_count > 0
)
SELECT
  geo_txt,
  ST_GEOGFROMTEXT(geo_txt) AS geo,
  commercial_count,
  target_count,
  ROUND(commercial_count / NULLIF(target_count, 0), 2) AS opportunity_score
FROM commercial_activity
WHERE target_count < THRESHOLD
  AND commercial_count > MIN_COMMERCIAL
ORDER BY opportunity_score DESC
LIMIT 20;
```

---

## Additional Resources

### Documentation
- [Places Insights API](https://developers.google.com/maps/documentation/placesinsights)
- [BigQuery Geospatial Functions](https://cloud.google.com/bigquery/docs/reference/standard-sql/geography_functions)
- [BigQuery Studio](https://cloud.google.com/bigquery/docs/bigquery-studio-intro)

### Support
- BigQuery Console: https://console.cloud.google.com/bigquery
- Dataset: `johanesa-playground-326616.places_insights___id.places`

---

**Document Version:** 1.0
**Last Updated:** October 27, 2025
**Maintained by:** Data Analytics Team
