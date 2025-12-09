-- ============================================================================
-- BONUS: NEAREST NEIGHBOR TSP SOLVER - Procedural Route Optimization
-- ============================================================================
-- This script demonstrates BigQuery's procedural capabilities using a
-- greedy nearest-neighbor algorithm to solve the Traveling Salesperson Problem.
--
-- Use Case: Find the optimal path for a single vehicle visiting 20 stops
-- Method: Iteratively select the closest unvisited stop
-- Note: This version uses K-Means to select stops from a specific zone
-- ============================================================================

-- IMPORTANT: Before running this query, you must:
-- 1. Run 00_create_kmeans_model.sql to create the model
-- 2. Replace 'your_project.your_dataset' with your actual values
-- 3. Optionally change zone_id filter to select different zones

BEGIN
  -- Declare variables
  DECLARE current_location GEOGRAPHY;
  DECLARE total_stops INT64;
  DECLARE counter INT64 DEFAULT 0;

  -- Create temporary table to store the optimized route
  CREATE TEMP TABLE optimized_route (
    stop_number INT64,
    station_id STRING,
    station_name STRING,
    location GEOGRAPHY,
    distance_from_previous_km FLOAT64
  );

  -- Create temporary table with stops from a specific K-Means zone
  CREATE TEMP TABLE remaining_stops AS
  WITH
    raw_stations AS (
      SELECT
        station_id,
        name,
        latitude,
        longitude,
        ST_GEOGPOINT(longitude, latitude) AS location
      FROM `bigquery-public-data.new_york_citibike.citibike_stations`
      WHERE is_renting = TRUE
        AND latitude BETWEEN 40.70 AND 40.82
        AND longitude BETWEEN -74.02 AND -73.93
    ),
    clustered_stations AS (
      SELECT
        s.station_id,
        s.name,
        s.location,
        p.CENTROID_ID AS zone_id
      FROM raw_stations s
      JOIN ML.PREDICT(
        MODEL `your_project.your_dataset.citibike_kmeans_model`,
        (SELECT * FROM raw_stations)
      ) p
      USING (station_id)
    )
  SELECT
    station_id,
    name,
    location
  FROM clustered_stations
  WHERE zone_id = 1  -- Change this to select different zones (0-9)
  LIMIT 20;

  -- Initialize: Start at the first stop
  SET current_location = (SELECT location FROM remaining_stops LIMIT 1);
  SET total_stops = (SELECT COUNT(*) FROM remaining_stops);

  -- Insert the starting point
  INSERT INTO optimized_route
  SELECT
    1 AS stop_number,
    station_id,
    name AS station_name,
    location,
    0.0 AS distance_from_previous_km
  FROM remaining_stops
  WHERE location = current_location;

  -- Remove the starting point from remaining stops
  DELETE FROM remaining_stops
  WHERE location = current_location;

  SET counter = 1;

  -- Main loop: Greedy nearest neighbor algorithm
  LOOP
    -- Exit condition
    IF counter >= total_stops THEN
      LEAVE;
    END IF;

    -- Find the nearest unvisited stop
    INSERT INTO optimized_route
    SELECT
      counter + 1 AS stop_number,
      station_id,
      name AS station_name,
      location,
      ROUND(ST_DISTANCE(current_location, location) / 1000, 2) AS distance_from_previous_km
    FROM remaining_stops
    ORDER BY ST_DISTANCE(current_location, location) ASC
    LIMIT 1;

    -- Update current location to the stop we just added
    SET current_location = (
      SELECT location
      FROM optimized_route
      WHERE stop_number = counter + 1
    );

    -- Remove the visited stop from remaining stops
    DELETE FROM remaining_stops
    WHERE location = current_location;

    SET counter = counter + 1;
  END LOOP;

  -- Output the optimized route for visualization
  SELECT
    stop_number,
    location AS geometry,
    'Stop' AS layer_type,
    CONCAT(
      '#', CAST(stop_number AS STRING), ': ',
      station_name, ' (+',
      CAST(distance_from_previous_km AS STRING), ' km)'
    ) AS label,
    distance_from_previous_km AS metric
  FROM optimized_route

  UNION ALL

  -- Add the route path
  SELECT
    NULL AS stop_number,
    ST_MAKELINE(ARRAY_AGG(location ORDER BY stop_number)) AS geometry,
    'Route Path' AS layer_type,
    CONCAT(
      'Total Distance: ',
      CAST(ROUND(SUM(distance_from_previous_km), 2) AS STRING),
      ' km'
    ) AS label,
    SUM(distance_from_previous_km) AS metric
  FROM optimized_route;

END;

-- ============================================================================
-- VISUALIZATION INSTRUCTIONS (BigQuery Geo Viz):
-- ============================================================================
-- 1. Go to https://bigquerygeoviz.appspot.com/
-- 2. Paste this script and click Run
-- 3. Configure styling:
--    - Geometry column: geometry
--    - Fill color: #4285F4 (Google Blue)
--    - Stroke width: 3 (for the route line)
--    - Circle radius: 6 (for stops)
--    - Fill opacity: 0.9
-- 4. Hover over stops to see the visit sequence and distances
-- ============================================================================

-- ============================================================================
-- ALTERNATIVE: View route details as a table
-- ============================================================================
-- To see the route as a table instead of a map, replace the final SELECT
-- with this query:

/*
SELECT
  stop_number,
  station_name,
  distance_from_previous_km,
  SUM(distance_from_previous_km) OVER (ORDER BY stop_number) AS cumulative_distance_km
FROM optimized_route
ORDER BY stop_number;
*/

-- ============================================================================
-- TALKING POINTS:
-- ============================================================================
-- 1. "This demonstrates BigQuery's procedural capabilities - LOOP, variables, temp tables"
-- 2. "K-Means pre-selected stops from a balanced territory, then we optimize the path"
-- 3. "The greedy nearest-neighbor algorithm finds a good (not optimal) solution quickly"
-- 4. "Each stop is chosen as the closest unvisited point from the current location"
-- 5. "This approach works for small routes (<100 stops)"
-- 6. "For larger problems, use the geohash heuristic or Google Maps API"
-- ============================================================================

-- ============================================================================
-- PERFORMANCE NOTES:
-- ============================================================================
-- - This script takes ~10-15 seconds to run for 20 stops
-- - Time complexity: O(n²) where n is the number of stops
-- - For production, consider:
--   * Geohash-based sequencing (instant, scales to millions)
--   * BQML for clustering + geohash for sequencing
--   * Google Maps API for exact optimization with traffic
-- ============================================================================
