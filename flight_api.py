# flight_api.py

from flask import Flask, request, jsonify
import requests
import os
from dotenv import load_dotenv

load_dotenv()
app = Flask(__name__)

# Retrieve API credentials from environment variables
AMADEUS_API_KEY = os.getenv("AMADEUS_API_KEY")
AMADEUS_API_SECRET = os.getenv("AMADEUS_API_SECRET")
AMADEUS_AUTH_URL = "https://test.api.amadeus.com/v1/security/oauth2/token"
AMADEUS_FLIGHTS_URL = "https://test.api.amadeus.com/v2/shopping/flight-offers"

def get_amadeus_token():
    """Fetches the Amadeus API access token using client credentials."""
    try:
        response = requests.post(AMADEUS_AUTH_URL, data={
            "grant_type": "client_credentials",
            "client_id": AMADEUS_API_KEY,
            "client_secret": AMADEUS_API_SECRET
        })
        print("Token response status:", response.status_code)  # Log status code
        response.raise_for_status()
        token = response.json()["access_token"]
        print("Token fetched successfully:", token)  # Log the token for verification
        return token
    except requests.exceptions.RequestException as e:
        print("Error fetching Amadeus token:", e)
        raise

@app.route('/api/flight-offers', methods=['GET'])
def flight_offers():
    """Handles requests to fetch flight offers based on provided parameters."""
    print("Received request for flight offers")  # Log when the endpoint is hit
    token = get_amadeus_token()
    origin = request.args.get('origin')
    destination = request.args.get('destination')
    departure_date = request.args.get('departure_date')

    # Log received parameters
    print("Parameters received - Origin:", origin, "Destination:", destination, "Departure Date:", departure_date)

    if not origin or not destination or not departure_date:
        print("Missing parameters")  # Log if any parameters are missing
        return jsonify({"error": "origin, destination, and departure_date are required"}), 400

    headers = {"Authorization": f"Bearer {token}"}
    params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": departure_date,
        "adults": 1
    }

    try:
        response = requests.get(AMADEUS_FLIGHTS_URL, headers=headers, params=params)
        print("Flight offers response status:", response.status_code)  # Log status code
        response.raise_for_status()
        data = response.json()
        
        # Limit to the top 5 offers based on any desired criteria
        best_offers = data['data'][:5]  # Limit the response to the top 5 results
        print("Best flight offers:", best_offers)  # Log the filtered offers

        return jsonify({"best_offers": best_offers})
    except requests.exceptions.RequestException as e:
        print("Error fetching flight offers:", e)  # Log if there's an error
        return jsonify({"error": "An error occurred while fetching flight offers"}), 500

if __name__ == '__main__':
    app.run(debug=True)
