-- ============================================================================
-- BQML K-Means Clustering for Route Optimization
-- ============================================================================
-- This script demonstrates using BigQuery ML to create balanced territories
-- using K-Means clustering. This is an OPTIONAL advanced approach.
--
-- For the demo, we recommend using geohash-based clustering (01_geohash_clustering.sql)
-- as it's faster and doesn't require model training.
-- ============================================================================

-- STEP 1: Create the K-Means Model
-- This is a one-time setup that trains a clustering model
-- Replace 'your_project.your_dataset' with your actual project and dataset

CREATE OR REPLACE MODEL `your_project.your_dataset.citibike_kmeans_model`
OPTIONS(
  model_type='kmeans',
  num_clusters=10,
  distance_type='euclidean',
  standardize_features=TRUE
) AS
SELECT
  latitude,
  longitude
FROM `bigquery-public-data.new_york_citibike.citibike_stations`
WHERE is_renting = TRUE
  AND latitude BETWEEN 40.70 AND 40.82
  AND longitude BETWEEN -74.02 AND -73.93;

-- STEP 2: Use the Model to Predict Clusters
-- This query assigns each station to a cluster (territory)

WITH clustered_stations AS (
  SELECT
    s.station_id,
    s.name,
    s.latitude,
    s.longitude,
    ST_GEOGPOINT(s.longitude, s.latitude) AS location,
    p.CENTROID_ID AS cluster_id
  FROM `bigquery-public-data.new_york_citibike.citibike_stations` s
  JOIN ML.PREDICT(
    MODEL `your_project.your_dataset.citibike_kmeans_model`,
    (
      SELECT
        station_id,
        latitude,
        longitude
      FROM `bigquery-public-data.new_york_citibike.citibike_stations`
      WHERE is_renting = TRUE
        AND latitude BETWEEN 40.70 AND 40.82
        AND longitude BETWEEN -74.02 AND -73.93
      LIMIT 500
    )
  ) p
  USING (station_id)
)

-- Output for visualization
SELECT
  cluster_id,
  location AS geometry,
  name AS label,
  'Station' AS type
FROM clustered_stations

UNION ALL

-- Add cluster centroids
SELECT
  cluster_id,
  ST_GEOGPOINT(
    AVG(longitude),
    AVG(latitude)
  ) AS geometry,
  CONCAT('Cluster ', CAST(cluster_id AS STRING)) AS label,
  'Centroid' AS type
FROM clustered_stations
GROUP BY cluster_id;

-- STEP 3: Evaluate Model Quality
-- Check how balanced the clusters are

SELECT
  CENTROID_ID AS cluster_id,
  COUNT(*) AS station_count,
  ROUND(AVG(latitude), 4) AS avg_lat,
  ROUND(AVG(longitude), 4) AS avg_lng
FROM ML.PREDICT(
  MODEL `your_project.your_dataset.citibike_kmeans_model`,
  (
    SELECT
      station_id,
      latitude,
      longitude
    FROM `bigquery-public-data.new_york_citibike.citibike_stations`
    WHERE is_renting = TRUE
      AND latitude BETWEEN 40.70 AND 40.82
      AND longitude BETWEEN -74.02 AND -73.93
  )
)
GROUP BY CENTROID_ID
ORDER BY CENTROID_ID;

-- STEP 4: Get Model Evaluation Metrics

SELECT
  *
FROM ML.EVALUATE(
  MODEL `your_project.your_dataset.citibike_kmeans_model`
);

-- ============================================================================
-- NOTES:
-- ============================================================================
-- 1. Model training takes 1-2 minutes
-- 2. The model is stored in BigQuery and can be reused
-- 3. K-Means creates more balanced clusters than geohash-based approaches
-- 4. For production, retrain the model periodically as data changes
-- 5. You can tune num_clusters based on your fleet size
-- ============================================================================
