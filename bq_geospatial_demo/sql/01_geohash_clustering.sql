-- ============================================================================
-- ACT 1: STRATEGIC PLANNING - Geohash-Based Territory Assignment
-- ============================================================================
-- This query demonstrates instant territory assignment using geohash prefixes.
-- No model training required - runs in milliseconds!
--
-- Use Case: Assign 500 delivery stops to 10 vehicle territories
-- Method: Group stations by geohash prefix for geographic clustering
-- ============================================================================

WITH
  -- Step 1: Load active stations in Manhattan
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
      -- Focus on Manhattan for clear visualization
      AND latitude BETWEEN 40.70 AND 40.82
      AND longitude BETWEEN -74.02 AND -73.93
    LIMIT 500
  ),

  -- Step 2: Assign territories using geohash clustering
  -- Geohash creates a spatial grid - nearby points share prefixes
  -- We use NTILE to create balanced groups from the sorted geohashes
  clustered_stations AS (
    SELECT
      station_id,
      name,
      location,
      latitude,
      longitude,
      capacity,
      ST_GEOHASH(location, 10) AS geohash,
      -- Create 10 balanced zones by partitioning sorted geohashes
      NTILE(10) OVER (ORDER BY ST_GEOHASH(location, 10)) AS zone_id
    FROM raw_stations
  ),

  -- Step 3: Calculate zone statistics
  zone_stats AS (
    SELECT
      zone_id,
      COUNT(*) AS station_count,
      SUM(capacity) AS total_capacity,
      -- Calculate the geographic center of each zone
      ST_CENTROID_AGG(location) AS zone_center
    FROM clustered_stations
    GROUP BY zone_id
  )

-- Output for BigQuery Geo Viz
-- Layer 1: Individual stations (points)
SELECT
  zone_id,
  location AS geometry,
  'Station' AS layer_type,
  name AS label,
  capacity AS metric
FROM clustered_stations

UNION ALL

-- Layer 2: Zone centers (centroids)
SELECT
  zone_id,
  zone_center AS geometry,
  'Zone Center' AS layer_type,
  CONCAT('Zone ', CAST(zone_id AS STRING), ' (', CAST(station_count AS STRING), ' stops)') AS label,
  station_count AS metric
FROM zone_stats;

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
--    - Circle radius: 5 (for points)
--    - Fill opacity: 0.8
-- 4. Use layer_type field to filter between Stations and Zone Centers
-- ============================================================================

-- ============================================================================
-- TALKING POINTS:
-- ============================================================================
-- 1. "We instantly divided 500 stops into 10 balanced territories"
-- 2. "This uses spatial indexing - no machine learning required"
-- 3. "Each color represents a delivery truck's territory"
-- 4. "The large dots show the geographic center of each zone"
-- 5. "This query costs less than $0.01 and runs in milliseconds"
-- ============================================================================
