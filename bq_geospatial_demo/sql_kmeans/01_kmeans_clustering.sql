-- ============================================================================
-- ACT 1: STRATEGIC PLANNING - BQML K-Means Territory Assignment
-- ============================================================================
-- This query demonstrates territory assignment using a trained K-Means model.
-- Requires model creation first (see 00_create_kmeans_model.sql)
--
-- Use Case: Assign 500 delivery stops to 10 vehicle territories
-- Method: Use BQML K-Means clustering for balanced geographic zones
-- ============================================================================

-- IMPORTANT: Before running this query, you must:
-- 1. Run 00_create_kmeans_model.sql to create the model
-- 2. Replace 'your_project.your_dataset' with your actual values

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

  -- Step 2: Assign territories using K-Means model predictions
  clustered_stations AS (
    SELECT
      s.station_id,
      s.name,
      s.location,
      s.latitude,
      s.longitude,
      s.capacity,
      -- Use the trained model to predict cluster assignments
      p.CENTROID_ID AS zone_id
    FROM raw_stations s
    JOIN ML.PREDICT(
      MODEL `your_project.your_dataset.citibike_kmeans_model`,
      (SELECT * FROM raw_stations)
    ) p
    USING (station_id)
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
-- 1. "We used machine learning to divide 500 stops into 10 balanced territories"
-- 2. "K-Means creates more geographically balanced clusters than simple sorting"
-- 3. "Each color represents a delivery truck's territory"
-- 4. "The large dots show the geographic center of each zone"
-- 5. "The model trains once in 1-2 minutes, then predictions are instant"
-- ============================================================================
