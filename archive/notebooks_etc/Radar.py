import json
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
import numpy as np
import folium

selected_file = "./samples/testing/samplecopy.json"

file = open(selected_file)
json_contents = json.load(file)
aircraft = json_contents["aircraft"]

planes = []

class PlaneLog:
    def __init__(self, hex):
        self.hex = hex
        self.planes = []
    def add_plane(self, plane_record):
        self.planes.append(plane_record)

for record in aircraft:
    matched_plane = False
    for plane in planes:
        if plane.hex == record["hex"]:
            plane.add_plane(record)
            matched_plane = True
    if matched_plane == False:
        new_plane = PlaneLog(record["hex"])
        new_plane.add_plane(record)
        planes.append(new_plane)
            
file.close()

print(f"🛫 Detected {len(planes)} planes!")
for i, plane in enumerate(planes):
    print(f"Plane #{i + 1}: {plane.hex} - {len(plane.planes)} records")

def find_plane(hex):
    for plane in planes:
        if plane.hex == hex:
            return plane
        
model = tf.keras.models.load_model("Model.keras")
model.summary()
print(model.input_shape, model.output_shape)
def handle_alt_baro(alt_baro):
    if alt_baro == "ground":
        return 0.0
    else:
        return alt_baro

def predict_adsb_data(adsb_message):
    try:
        feature_vector = [
            handle_alt_baro(adsb_message.get('alt_baro', 0)),
            #float(adsb_message.get('alt_baro', 0)),
            float(adsb_message.get('gs', 0)),
            float(adsb_message.get('track', 0)),
            float(adsb_message.get('baro_rate', 0)),
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

    # scaler = StandardScaler()
    # features_scaled = scaler.fit_transform([feature_vector])
    # prediction = model.predict(np.array(features_scaled))

    prediction = model.predict(np.array([feature_vector]))
    return prediction[0][0]
    #return int(round(prediction[0][0]))
    
from IPython.display import display
m = folium.Map(location = [51.5800, 5.1875], tiles ='OpenStreetMap', zoom_start=3, max_bounds=True, min_zoom=2)

#scaler = StandardScaler()

for plane in planes:
    print(plane.hex)
    aircraft_data = find_plane(plane.hex)
    if aircraft_data == None:
        continue
        
    results = predict_adsb_data(aircraft_data.planes[0])
    print(f'[RESULTS: {results}]')
    spoofed = (True if results > 0.5 else False)
    percentage = results * 100

    text = ("Spoofed" if spoofed else "Not Spoofed")
    print(f"{text} -#-- {percentage}% prediction of being spoofed")
    
    plane_values = [{"key": "hex", "value": "Hex (24-bit ICAO identifier)"}, {"key": "type", "value": "Data Source"}, {"key": "flight", "value": "Flight Callsign"}, {"key": "r", "value": "Aircraft Registration"}, {"key": "t", "value": "Aircraft Type"}, {"key": "alt_baro", "value": "Aircraft Barometric Altitude (feet)"}, {"key": "gs", "value": "Ground Speed (knots)"}, {"key": "track", "value": "True Track (degrees)"}, {"key": "baro_rate", "value": "Rate of Change of Barometric Altitude (feet/minute)"}, {"key": "lat", "value": "Latitude"}, {"key": "lon", "value": "Longitude"}, {"key": "seen_pos", "value": "Updated Time Ago (seconds)"}, {"key": "messages", "value": "Total # of Mode S Messages"}, {"key": "seen", "value": "Last Timing Message (seconds)"}, {"key": "rssi", "value": "Signal Power (dbFs)"}]
    
    def find_value(id):
        for x in plane_values:
            if x["key"] == id:
                return x

    plane_data = aircraft_data.planes[0]
    plane_coordinates = (plane_data["lat"], plane_data["lon"])

    # Draw map markers
    folium.CircleMarker(
        location=plane_coordinates,
        radius=5,
        color=("red" if spoofed else "green"),
        fill=True,
        fill_color=("red" if spoofed else "green"),
        fill_opacity=0.7,
        popup='Flight: ' + aircraft_data.planes[0]['flight'] + '<br>Hex: ' + plane.hex + '<br>Lat: ' + str(aircraft_data.planes[0]['lat']) + '<br>Lon: ' + str(aircraft_data.planes[0]['lon'])
    ).add_to(m)

display(m)