"""
Google Cloud Function: Route Optimization Bridge
This function acts as a bridge between BigQuery and Google Maps API.
It receives waypoints from BigQuery and returns optimized routes from Maps API.
"""

import json
import os

import functions_framework
import googlemaps

# Initialize Google Maps client
# In production, use Secret Manager instead of environment variables
MAPS_API_KEY = os.environ.get('MAPS_API_KEY', '')
gmaps = googlemaps.Client(key=MAPS_API_KEY)


@functions_framework.http
def optimize_route(request):
    """
    Optimize a route using Google Maps Directions API.

    BigQuery Remote Functions send requests in this format:
    {
      "calls": [
        [
          [{"lat": 40.7, "lng": -73.9}, {"lat": 40.71, "lng": -73.91}, ...]
        ]
      ]
    }

    Returns:
    {
      "replies": [
        "{\"polyline\": \"...\", \"duration\": \"...\", \"distance\": \"...\"}"
      ]
    }
    """
    try:
        # Parse the request from BigQuery
        request_json = request.get_json()

        if not request_json or 'calls' not in request_json:
            return {
                'errorMessage': 'Invalid request format. Expected {"calls": [...]}'
            }, 400

        calls = request_json['calls']
        results = []

        # Process each call (BigQuery can batch multiple requests)
        for call in calls:
            # Extract the stops array from the call
            # BigQuery sends: [[stops_array]]
            if not call or len(call) == 0:
                results.append(json.dumps({"error": "Empty call"}))
                continue

            stops = call[0]

            # Validate input
            if not stops or not isinstance(stops, list) or len(stops) < 2:
                results.append(json.dumps({
                    "error": "Need at least 2 stops to create a route"
                }))
                continue

            # Prepare the Maps API request
            origin = (stops[0]['lat'], stops[0]['lng'])
            destination = (stops[-1]['lat'], stops[-1]['lng'])

            # Middle stops become waypoints
            waypoints = [(s['lat'], s['lng'])
                         for s in stops[1:-1]] if len(stops) > 2 else None

            # Call Google Maps Directions API
            # optimize_waypoints=True enables the TSP solver
            try:
                directions = gmaps.directions(
                    origin=origin,
                    destination=destination,
                    waypoints=waypoints,
                    optimize_waypoints=True,
                    mode='driving',
                    departure_time='now'  # Get real-time traffic data
                )

                if directions and len(directions) > 0:
                    route = directions[0]

                    # Extract the encoded polyline and metrics
                    polyline = route['overview_polyline']['points']

                    # Calculate total duration and distance across all legs
                    total_duration_seconds = sum(
                        leg['duration']['value'] for leg in route['legs']
                    )
                    total_distance_meters = sum(
                        leg['distance']['value'] for leg in route['legs']
                    )

                    # Format the response
                    results.append(json.dumps({
                        "polyline": polyline,
                        "duration": f"{total_duration_seconds // 60} mins",
                        "distance": f"{total_distance_meters / 1000:.2f} km",
                        "duration_seconds": total_duration_seconds,
                        "distance_meters": total_distance_meters,
                        "waypoint_order": route.get('waypoint_order', [])
                    }))
                else:
                    results.append(json.dumps({
                        "error": "No route found by Google Maps API"
                    }))

            except googlemaps.exceptions.ApiError as e:
                results.append(json.dumps({
                    "error": f"Maps API error: {str(e)}"
                }))
            except Exception as e:
                results.append(json.dumps({
                    "error": f"Unexpected error calling Maps API: {str(e)}"
                }))

        # Return results in BigQuery Remote Function format
        return {'replies': results}

    except Exception as e:
        # Return error in BigQuery Remote Function format
        return {
            'errorMessage': f"Function error: {str(e)}"
        }, 500


# For local testing
if __name__ == '__main__':
    # Test data
    test_request = {
        'calls': [
            [
                [
                    {'lat': 40.7589, 'lng': -73.9851},
                    {'lat': 40.7614, 'lng': -73.9776},
                    {'lat': 40.7580, 'lng': -73.9855}
                ]
            ]
        ]
    }

    class MockRequest:
        def get_json(self):
            return test_request

    result = optimize_route(MockRequest())
    print(json.dumps(result, indent=2))
