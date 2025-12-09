-- ============================================================================
-- ACT 3: OPERATIONAL EXECUTION - Google Maps API Integration
-- ============================================================================
-- This query demonstrates the "Hybrid Architecture" by combining BigQuery's
-- strategic planning with Google Maps API's tactical execution.
--
-- PREREQUISITES:
-- 1. Deploy the Cloud Function (see cloud_function/ directory)
-- 2. Create BigQuery Remote Function connection
-- 3. Update the placeholders below with your project details
-- ============================================================================

-- ============================================================================
-- STEP 1: Create the Remote Function (ONE-TIME SETUP)
-- ============================================================================
-- Run this once to register the Cloud Function as a BigQuery function
-- Replace the placeholders with your actual values

CREATE OR REPLACE FUNCTION `johanesa-playground-326616.demo_dataset.optimize_route`(
  stops_json STRING
)
RETURNS STRING
REMOTE WITH CONNECTION `johanesa-playground-326616.us.gmaps_conn`
OPTIONS (
  endpoint = 'https://us-central1-johanesa-playground-326616.cloudfunctions.net/optimize-route',
  max_batching_rows = 1
);

-- ============================================================================
-- STEP 2: The Hybrid Query - BigQuery + Google Maps
-- ============================================================================

WITH
  -- ACT 1: STRATEGIC PLANNING (BigQuery)
  -- Cluster 500 stops into 10 territories
  raw_stations AS (
    SELECT
      station_id,
      name,
      latitude,
      longitude,
      ST_GEOGPOINT(longitude, latitude) AS location
    FROM `bigquery-public-data.new_york_citibike.citibike_stations`
    WHERE is_renting = TRUE
      AND capacity > 0
      AND latitude BETWEEN 40.70 AND 40.82
      AND longitude BETWEEN -74.02 AND -73.93
    LIMIT 100
  ),

  clustered_stations AS (
    SELECT
      station_id,
      name,
      location,
      latitude,
      longitude,
      NTILE(10) OVER (ORDER BY ST_GEOHASH(location, 10)) AS zone_id
    FROM raw_stations
  ),

  -- ACT 2: TACTICAL SEQUENCING (BigQuery)
  -- Order stops using spatial indexing
  sequenced_stations AS (
    SELECT
      zone_id,
      station_id,
      name,
      location,
      latitude,
      longitude,
      ROW_NUMBER() OVER (
        PARTITION BY zone_id
        ORDER BY ST_GEOHASH(location, 15)
      ) AS stop_sequence
    FROM clustered_stations
  ),

  -- Create BigQuery route paths (straight lines)
  bq_routes AS (
    SELECT
      zone_id,
      ST_MAKELINE(ARRAY_AGG(location ORDER BY stop_sequence)) AS bq_route_geometry,
      ROUND(
        ST_LENGTH(ST_MAKELINE(ARRAY_AGG(location ORDER BY stop_sequence))) / 1000,
        2
      ) AS bq_route_distance_km
    FROM sequenced_stations
    GROUP BY zone_id
  ),

  -- ACT 3: OPERATIONAL EXECUTION (Google Maps API)
  -- Prepare data for Maps API - send only Zone 1 to save API quota
  api_input AS (
    SELECT
      zone_id,
      ARRAY_AGG(
        STRUCT(latitude AS lat, longitude AS lng)
        ORDER BY stop_sequence
      ) AS waypoints
    FROM sequenced_stations
    WHERE zone_id = 1  -- Demo: Only optimize one zone
    GROUP BY zone_id
  ),

  -- Call the Google Maps API via Remote Function
  api_response AS (
    SELECT
      zone_id,
      waypoints,
      `johanesa-playground-326616.demo_dataset.optimize_route`(TO_JSON_STRING(waypoints)) AS maps_response
    FROM api_input
  ),

  -- Parse the API response
  maps_routes AS (
    SELECT
      zone_id,
      -- Parse the GeoJSON from Maps API response
      ST_GEOGFROMGEOJSON(
        FORMAT('%s', JSON_QUERY(maps_response, '$.geojson'))
      ) AS maps_route_geometry,
      JSON_EXTRACT_SCALAR(maps_response, '$.duration') AS maps_duration,
      JSON_EXTRACT_SCALAR(maps_response, '$.distance') AS maps_distance
    FROM api_response
  )

-- ============================================================================
-- OUTPUT: Compare BigQuery vs Google Maps routes
-- ============================================================================

-- Layer 1: Individual stops
SELECT
  zone_id,
  location AS geometry,
  'Stop' AS layer_type,
  CONCAT(name, ' (#', CAST(stop_sequence AS STRING), ')') AS label,
  'BigQuery' AS source
FROM sequenced_stations

UNION ALL

-- Layer 2: BigQuery route (straight lines - "as the crow flies")
SELECT
  zone_id,
  bq_route_geometry AS geometry,
  'BigQuery Route' AS layer_type,
  CONCAT(
    'BQ Route: ', CAST(bq_route_distance_km AS STRING), ' km (geodesic)'
  ) AS label,
  'BigQuery' AS source
FROM bq_routes

UNION ALL

-- Layer 3: Google Maps route (road network - "as the car drives")
SELECT
  zone_id,
  maps_route_geometry AS geometry,
  'Google Maps Route' AS layer_type,
  CONCAT(
    'Maps Route: ', maps_distance, ', ', maps_duration
  ) AS label,
  'Google Maps' AS source
FROM maps_routes;

-- ============================================================================
-- VISUALIZATION INSTRUCTIONS (BigQuery Geo Viz):
-- ============================================================================
-- 1. Go to https://bigquerygeoviz.appspot.com/
-- 2. Paste this query and click Run
-- 3. Configure styling:
--
--    - Geometry column: geometry
--    - Fill color: Data-driven
--      - Field: source
--      - Function: categorical
--        - BigQuery: Red (#EA4335)
--        - Google Maps: Blue (#4285F4)
--    - Stroke width: 3 (for routes)
--    - Fill opacity: 0.9
--
-- 4. Toggle layer_type to compare:
--    - BigQuery Route: Straight lines (strategic planning)
--    - Google Maps Route: Road network (operational execution)
--
-- 5. Notice the difference:
--    - BigQuery: Fast, cheap, good for planning
--    - Google Maps: Precise, traffic-aware, ready for drivers
-- ============================================================================

-- ============================================================================
-- ALTERNATIVE: Side-by-side comparison
-- ============================================================================
-- Uncomment this to see a table comparing both approaches

/*
SELECT
  'BigQuery (Strategic)' AS approach,
  bq_route_distance_km AS distance_km,
  NULL AS duration,
  'Geodesic (straight line)' AS method,
  '<$0.01' AS cost
FROM bq_routes
WHERE zone_id = 1

UNION ALL

SELECT
  'Google Maps (Tactical)' AS approach,
  CAST(REGEXP_EXTRACT(maps_distance, r'([\d.]+)') AS FLOAT64) AS distance_km,
  maps_duration AS duration,
  'Road network with traffic' AS method,
  '~$0.005' AS cost
FROM maps_routes
WHERE zone_id = 1;
*/

-- ============================================================================
-- TALKING POINTS:
-- ============================================================================
-- 1. "The red line is BigQuery's strategic plan - instant and cheap"
-- 2. "The blue line is Google Maps' tactical execution - precise and driveable"
-- 3. "Notice how the blue line follows actual roads, not straight lines"
-- 4. "BigQuery processed 100 stops in milliseconds for fractions of a cent"
-- 5. "We only sent the final 10 stops to Maps API - cost optimization"
-- 6. "This hybrid approach gives us both speed and precision"
-- ============================================================================

-- ============================================================================
-- DEPLOYMENT CHECKLIST:
-- ============================================================================
-- [ ] Cloud Function deployed with Maps API key
-- [ ] BigQuery connection created (gmaps_conn)
-- [ ] Service account granted Cloud Functions Invoker role
-- [ ] Remote function created (Step 1 above)
-- [ ] Project/dataset placeholders replaced in this file
-- [ ] Test with small dataset first (LIMIT 20)
-- ============================================================================
