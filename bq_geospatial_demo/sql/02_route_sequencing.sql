-- ============================================================================
-- ACT 2: TACTICAL SEQUENCING - Route Ordering with Spatial Indexing
-- ============================================================================
-- This query demonstrates route sequencing within each territory.
-- It creates a logical visit order and generates route paths.
--
-- Use Case: Order stops within each territory for efficient routing
-- Method: Use geohash sorting to create a "traveling path" through nearby points
-- ============================================================================

WITH
  -- Step 1: Load and cluster stations
  raw_stations AS (
    SELECT
      station_id,
      name,
      latitude,
      longitude,
      ST_GEOGPOINT(longitude, latitude) AS location,
      capacity
    FROM `bigquery-public-data.new_york_citibike.citibike_stations`
    WHERE is_renting = TRUE
      AND capacity > 0
      AND latitude BETWEEN 40.70 AND 40.82
      AND longitude BETWEEN -74.02 AND -73.93
    LIMIT 500
  ),

  -- Step 2: Assign territories
  clustered_stations AS (
    SELECT
      station_id,
      name,
      location,
      latitude,
      longitude,
      capacity,
      NTILE(10) OVER (ORDER BY ST_GEOHASH(location, 10)) AS zone_id
    FROM raw_stations
  ),

  -- Step 3: Sequence stops within each territory
  -- Geohash sorting creates a "snake pattern" through nearby points
  sequenced_stations AS (
    SELECT
      zone_id,
      station_id,
      name,
      location,
      capacity,
      -- Create visit sequence using geohash ordering
      ROW_NUMBER() OVER (
        PARTITION BY zone_id
        ORDER BY ST_GEOHASH(location, 15)
      ) AS stop_sequence
    FROM clustered_stations
  ),

  -- Step 4: Generate route paths for each zone
  route_paths AS (
    SELECT
      zone_id,
      COUNT(*) AS stop_count,
      -- Connect stops in sequence order to create a route line
      ST_MAKELINE(ARRAY_AGG(location ORDER BY stop_sequence)) AS route_geometry,
      -- Calculate total route distance in kilometers
      ROUND(
        ST_LENGTH(ST_MAKELINE(ARRAY_AGG(location ORDER BY stop_sequence))) / 1000,
        2
      ) AS route_distance_km
    FROM sequenced_stations
    GROUP BY zone_id
  )

-- Output for BigQuery Geo Viz
-- Layer 1: Individual stops with sequence numbers
SELECT
  zone_id,
  location AS geometry,
  'Stop' AS layer_type,
  CONCAT(name, ' (#', CAST(stop_sequence AS STRING), ')') AS label,
  stop_sequence AS metric
FROM sequenced_stations

UNION ALL

-- Layer 2: Route paths (straight lines connecting stops)
SELECT
  zone_id,
  route_geometry AS geometry,
  'Route Path' AS layer_type,
  CONCAT(
    'Zone ', CAST(zone_id AS STRING),
    ': ', CAST(stop_count AS STRING), ' stops, ',
    CAST(route_distance_km AS STRING), ' km'
  ) AS label,
  route_distance_km AS metric
FROM route_paths;

-- ============================================================================
-- VISUALIZATION INSTRUCTIONS (BigQuery Geo Viz):
-- ============================================================================
-- 1. Go to https://bigquerygeoviz.appspot.com/
-- 2. Paste this query and click Run
-- 3. Configure styling:
--    - Geometry column: geometry
--    - Fill color: Data-driven
--      - Field: zone_id
--      - Function: categorical
--    - Stroke width: 2 (for lines)
--    - Fill opacity: 0.8
-- 4. Toggle layer_type to show/hide Stops vs Route Paths
-- 5. Look for the "snake pattern" - stops are visited in geographic order
-- ============================================================================

-- ============================================================================
-- ALTERNATIVE: View route statistics
-- ============================================================================
-- Uncomment this query to see route metrics instead of visualization

/*
SELECT
  zone_id,
  stop_count,
  route_distance_km,
  ROUND(route_distance_km / stop_count, 2) AS avg_km_per_stop
FROM route_paths
ORDER BY zone_id;
*/

-- ============================================================================
-- TALKING POINTS:
-- ============================================================================
-- 1. "Each colored line is a delivery route for one truck"
-- 2. "Stops are ordered using spatial indexing - nearby stops are visited together"
-- 3. "This creates a 'snake pattern' that minimizes backtracking"
-- 4. "The straight lines show geodesic distance - 'as the crow flies'"
-- 5. "In Act 3, we'll replace these with real road network paths"
-- 6. "This approach scales to millions of points instantly"
-- ============================================================================
