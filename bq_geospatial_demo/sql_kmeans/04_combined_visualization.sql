-- ============================================================================
-- COMBINED VISUALIZATION - All Demo Layers in One Query (K-Means Version)
-- ============================================================================
-- This query combines K-Means territory assignment, route sequencing, and
-- statistics into a single visualization for BigQuery Geo Viz.
--
-- Use Case: Show the complete logistics optimization in one view
-- Layers: Stops, Zone Centers, Route Paths, Statistics
-- ============================================================================

-- IMPORTANT: Before running this query, you must:
-- 1. Run 00_create_kmeans_model.sql to create the model
-- 2. Replace 'your_project.your_dataset' with your actual values

WITH
  -- Step 1: Load active stations
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

  -- Step 2: Assign territories using K-Means model
  clustered_stations AS (
    SELECT
      s.station_id,
      s.name,
      s.location,
      s.latitude,
      s.longitude,
      s.capacity,
      p.CENTROID_ID AS zone_id
    FROM raw_stations s
    JOIN ML.PREDICT(
      MODEL `your_project.your_dataset.citibike_kmeans_model`,
      (SELECT * FROM raw_stations)
    ) p
    USING (station_id)
  ),

  -- Step 3: Sequence stops within each territory
  sequenced_stations AS (
    SELECT
      zone_id,
      station_id,
      name,
      location,
      capacity,
      ROW_NUMBER() OVER (
        PARTITION BY zone_id
        ORDER BY ST_GEOHASH(location, 15)
      ) AS stop_sequence
    FROM clustered_stations
  ),

  -- Step 4: Generate route paths
  route_paths AS (
    SELECT
      zone_id,
      COUNT(*) AS stop_count,
      ST_MAKELINE(ARRAY_AGG(location ORDER BY stop_sequence)) AS route_geometry,
      ROUND(
        ST_LENGTH(ST_MAKELINE(ARRAY_AGG(location ORDER BY stop_sequence))) / 1000,
        2
      ) AS route_distance_km
    FROM sequenced_stations
    GROUP BY zone_id
  ),

  -- Step 5: Calculate zone centers
  zone_centers AS (
    SELECT
      zone_id,
      ST_CENTROID_AGG(location) AS center_location,
      COUNT(*) AS station_count,
      SUM(capacity) AS total_capacity
    FROM sequenced_stations
    GROUP BY zone_id
  )

-- ============================================================================
-- OUTPUT: Multiple layers for visualization
-- ============================================================================

-- Layer 1: Individual stops (points)
SELECT
  zone_id,
  location AS geometry,
  'Stop' AS layer_type,
  CONCAT(name, ' (#', CAST(stop_sequence AS STRING), ')') AS label,
  stop_sequence AS sequence_number,
  capacity AS capacity_value
FROM sequenced_stations

UNION ALL

-- Layer 2: Route paths (lines)
SELECT
  zone_id,
  route_geometry AS geometry,
  'Route Path' AS layer_type,
  CONCAT(
    'Zone ', CAST(zone_id AS STRING),
    ': ', CAST(stop_count AS STRING), ' stops, ',
    CAST(route_distance_km AS STRING), ' km'
  ) AS label,
  NULL AS sequence_number,
  route_distance_km AS capacity_value
FROM route_paths

UNION ALL

-- Layer 3: Zone centers (centroids)
SELECT
  zone_id,
  center_location AS geometry,
  'Zone Center' AS layer_type,
  CONCAT(
    'Zone ', CAST(zone_id AS STRING), ' Center',
    ' (', CAST(station_count AS STRING), ' stops, ',
    CAST(total_capacity AS STRING), ' capacity)'
  ) AS label,
  NULL AS sequence_number,
  total_capacity AS capacity_value
FROM zone_centers;

-- ============================================================================
-- VISUALIZATION INSTRUCTIONS (BigQuery Geo Viz):
-- ============================================================================
-- 1. Go to https://bigquerygeoviz.appspot.com/
-- 2. Paste this query and click Run
-- 3. Configure styling:
--
--    GLOBAL SETTINGS:
--    - Geometry column: geometry
--    - Fill color: Data-driven
--      - Field: zone_id
--      - Function: categorical
--    - Fill opacity: 0.8
--
--    LAYER-SPECIFIC SETTINGS (use layer_type to filter):
--    - Stops: Circle radius 4, show labels on hover
--    - Route Path: Stroke width 2, no fill
--    - Zone Center: Circle radius 8, bold labels
--
-- 4. Use the layer_type field to toggle layers on/off
-- 5. Color coding shows which stops belong to which zone
-- ============================================================================

-- ============================================================================
-- ALTERNATIVE: Summary Statistics
-- ============================================================================
-- Uncomment this query to see summary statistics instead of the map

/*
SELECT
  rp.zone_id,
  rp.stop_count,
  rp.route_distance_km,
  ROUND(rp.route_distance_km / rp.stop_count, 2) AS avg_km_per_stop,
  zc.total_capacity,
  ROUND(zc.total_capacity / rp.stop_count, 1) AS avg_capacity_per_stop
FROM route_paths rp
JOIN zone_centers zc USING (zone_id)
ORDER BY zone_id;
*/

-- ============================================================================
-- TALKING POINTS:
-- ============================================================================
-- 1. "This single query shows the complete optimization pipeline using K-Means"
-- 2. "10 color-coded territories created by machine learning"
-- 3. "The large dots are zone centers - optimal depot locations"
-- 4. "K-Means creates more balanced territories than simple geohash sorting"
-- 5. "Total processing time: under 1 second (after model is trained)"
-- 6. "This scales to millions of points with the same approach"
-- ============================================================================

-- ============================================================================
-- DEMO FLOW SUGGESTION:
-- ============================================================================
-- 1. First, show only "Stop" layer - raw data points
-- 2. Add "Zone Center" layer - show K-Means clustering result
-- 3. Add "Route Path" layer - show the complete solution
-- 4. Toggle between layers to explain each step
-- 5. Zoom into one zone to show the detailed route sequence
-- 6. Compare with geohash version to show improved balance
-- ============================================================================
