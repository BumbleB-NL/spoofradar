import requests
from flask import Flask, render_template, jsonify
import json
import tensorflow as tf
import numpy as np
import threading
import time
import os

app = Flask(__name__)

# Load your model (adjust the path if necessary)
model = tf.keras.models.load_model("ModelV4.keras")

# Store precomputed results in memory
cached_predictions = []

# Used for testing only
def get_aircraft_data():
    # selected_file = "./samples/testing/sample.json"
    # selected_file = "./samples/testing/sample_incomplete.json"
    # selected_file = "./samples/testing/sample_custom.json"
    # selected_file = "./samples/testing/dumpsample.json"
    selected_file = os.getenv("TEST_FILE", "./samples/testing/sample_custom.json")
    with open(selected_file) as file:
        json_contents = json.load(file)
    return json_contents["aircraft"]

# Function to fetch aircraft data from a web endpoint
def get_aircraft_data_from_endpoint():
    endpoint_url = os.getenv("DUMP1090_ENDPOINT", "http://dump1090:8080/data/aircraft.json")
    print("Getting data from: " + endpoint_url)
    try:
        response = requests.get(endpoint_url)
        response.raise_for_status()  # Raise an error for bad responses (e.g., 404, 500)
        json_contents = response.json()
        return json_contents.get("aircraft", [])
    except requests.RequestException as e:
        print(f"Error fetching data from endpoint: {e}")
        return []

# Function to validate if a record has all necessary fields for the AI model
def is_valid_record(record):
    required_fields = [
        'altitude', 'alt_baro', 'speed', 'gs', 'track', 'vert_rate', 'baro_rate',
        'lat', 'lon', 'seen_pos', 'messages', 'seen', 'rssi'
    ]
    return any(record.get(field) is not None for field in required_fields) and all(
        field in record for field in ['lat', 'lon']
    )

def handle_alt_baro(alt_baro, altitude):
    if alt_baro == "ground":
        return 0.0  # Return 0.0 if the alt_baro is marked as "ground"
    if altitude == "ground":
        return 0.0
    return alt_baro if alt_baro is not None else (altitude if altitude is not None else 0.0)


def handle_baro_rate(vert_rate, baro_rate):
    return vert_rate if vert_rate is not None else (baro_rate if baro_rate is not None else 0.0)

def handle_speed(speed, gs):
    return speed if speed is not None else (gs if gs is not None else 0.0)

def predict_adsb_data(adsb_message):
    try:
        feature_vector = [
            handle_alt_baro(adsb_message.get('alt_baro'), adsb_message.get('altitude')),
            float(handle_speed(adsb_message.get('speed'), adsb_message.get('gs'))),
            float(adsb_message.get('track', 0)),
            float(handle_baro_rate(adsb_message.get('vert_rate'), adsb_message.get('baro_rate'))),
            float(adsb_message.get('lat', 0)),
            float(adsb_message.get('lon', 0)),
            float(adsb_message.get('seen_pos', 0)),
            float(adsb_message.get('messages', 0)),
            float(adsb_message.get('seen', 0)),
            float(adsb_message.get('rssi', 0)),
        ]
    except ValueError as e:
        print(f"Error processing ADS-B message: {adsb_message}, Field: {e}")
        return None

    prediction = model.predict(np.array([feature_vector]), verbose=0)
    return prediction[0][0]

# Background task to periodically update cached predictions
def update_predictions(interval=5):
    global cached_predictions
    while True:
        testingMode = os.getenv("TEST_MODE", "True").lower() in ('true', '1', 't')
        if testingMode:
            aircraft = get_aircraft_data()
        else:
            aircraft = get_aircraft_data_from_endpoint()
            
        valid_aircraft = [record for record in aircraft if is_valid_record(record)]

        planes = []
        class PlaneLog:
            def __init__(self, hex):
                self.hex = hex
                self.planes = []
            def add_plane(self, plane_record):
                self.planes.append(plane_record)

        # Organize data by plane
        for record in valid_aircraft:
            matched_plane = False
            for plane in planes:
                if plane.hex == record["hex"]:
                    plane.add_plane(record)
                    matched_plane = True
            if not matched_plane:
                new_plane = PlaneLog(record["hex"])
                new_plane.add_plane(record)
                planes.append(new_plane)

        # Compute predictions
        updated_data = []
        for plane in planes:
            aircraft_data = plane.planes[0]  # Use the first record for simplicity
            prediction = predict_adsb_data(aircraft_data)
            
            prediction2 = float(prediction)

            # Add the prediction to the data
            updated_data.append({
                'alt': float(handle_alt_baro(aircraft_data.get('alt_baro'), aircraft_data.get('altitude'))),
                'lat': float(aircraft_data["lat"]),
                'lon': float(aircraft_data["lon"]),
                'flight': aircraft_data.get("flight", "Unknown"),
                'hex': plane.hex,
                'prediction': prediction2
            })

        # Cache the results in memory
        cached_predictions = updated_data

        # Wait for the next interval
        time.sleep(interval)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_aircraft_data')
def get_aircraft_data_endpoint():
    return jsonify(cached_predictions)

if __name__ == "__main__":
    # Start the background thread
    threading.Thread(target=update_predictions, daemon=True).start()

    # Run the Flask app
    app.run(host='0.0.0.0', port=80, debug=True)
