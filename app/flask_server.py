from flask import Flask, request, redirect, jsonify, url_for, render_template, flash
import json
from werkzeug.utils import secure_filename
import os
import pandas as pd
import plotly.graph_objects as go
import requests
from datetime import datetime, timezone

UPLOAD_FOLDER = 'uploads'
DATA_FOLDER = 'data'
ALLOWED_EXTENSIONS = {'json'}

app = Flask(__name__)

app.config['DATA_FOLDER'] = DATA_FOLDER
app.secret_key = 'supersecretkey'  # For flash messages


# # Function to check if the uploaded file is allowed
# def allowed_file(filename):
#     return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def has_minimum_8_days_of_data(power_data):

    # Convert UNIX timestamps to timezone-aware datetime objects in UTC and extract the dates
    dates = set()
    for timestamp in power_data.keys():
        # Use timezone-aware datetime with UTC
        date = datetime.fromtimestamp(int(timestamp) / 1000, tz=timezone.utc).date()
        dates.add(date)

    # Check if there are at least 8 unique dates
    return len(dates) >= 8

# Route to handle file upload
# @app.route('/upload', methods=['POST'])
# def upload_file():
#     if 'file' not in request.files:
#         flash('No file uploaded')
#         return redirect(request.url)

#     file = request.files['file']
#     if file.filename == '':
#         flash('No file selected')
#         return redirect(request.url)

#     if file and allowed_file(file.filename):
#         filename = secure_filename(file.filename)
#         filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
#         file.save(filepath)

#         # Load the file content as JSON
#         with open(filepath, 'r') as f:
#             data = json.load(f)

#         flash('File successfully uploaded and processed')
#         get_load_forecast(data)
#         return render_template('upload.html', data=data)

#     flash('Invalid file, please upload a JSON file')
#     return redirect(request.url)


# Display the upload form
@app.route('/efp')
def upload_form():
    return render_template('upload.html')


# Display results (after processing)
@app.route('/efp/display')
def display_results():
    return render_template('efp_prediction.html')


# Save PV configurations
@app.route('/efp/pv-config/<lat>/<lon>/<dec>/<az>/<kwp>', methods=['POST'])
def set_pv_configurations(lat, lon, dec, az, kwp):
    form_data = {
        'latitude': lat,
        'longitude': lon,
        'declination': dec,
        'azimuth': az,
        'kwp': kwp
    }

    data_filepath = os.path.join(app.config['DATA_FOLDER'], 'form_data.json')
    with open(data_filepath, 'w') as json_file:
        json.dump(form_data, json_file)

    return jsonify({"message": "PV configuration saved successfully!"})


# Handle form submission and save PV data
@app.route('/pv-config', methods=['POST'])
def submit_data():
    latitude = request.form['latitude']
    longitude = request.form['longitude']
    declination = request.form['declination']
    azimuth = request.form['azimuth']
    kwp = request.form['kwp']

    form_data = {
        'latitude': latitude,
        'longitude': longitude,
        'declination': declination,
        'azimuth': azimuth,
        'kwp': kwp
    }

    data_filepath = os.path.join(app.config['DATA_FOLDER'], 'form_data.json')
    with open(data_filepath, 'w') as json_file:
        json.dump(form_data, json_file)

    flash('Form data successfully saved!')
    return redirect(url_for('upload_form'))


# Predict energy consumption based on uploaded file
@app.route('/efp/predict', methods=['POST'])
def get_predictions_forecast():
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    load_history = json.load(file)

    # Extract power data from the JSON
    power_data = load_history.get('power', {})

    # Check if there are at least 8 days of historical data
    if not has_minimum_8_days_of_data(power_data):
        return jsonify({"error": "Insufficient historical data. At least 8 days are required."}), 400

    #
    get_load_forecast(load_history)
    load_forecast = load_load_forecast_data()
    df_load_forecast = process_load_forecast_data(load_forecast)

    # Check if "data/form_data.json" exists
    form_data_path = os.path.join(app.config['DATA_FOLDER'], 'form_data.json')
    if not os.path.exists(form_data_path):
        return jsonify({"error": "PV configuration not found."}), 400

    pv_data = load_pv_form_data()
    lat, lon, dec, az, kwp = (
        pv_data["latitude"],
        pv_data["longitude"],
        pv_data["declination"],
        pv_data["azimuth"],
        pv_data["kwp"]
    )

    print("[*] Calling Solar Forecast API", flush=True)
    try:
        get_pv_forecast(lat, lon, dec, az, kwp)
    except:
        print("[*] Can't reach Solar Forecast API", flush=True)
    finally:
        pv_forecast = load_pv_forecast_data()

    print("[*] Saving Solar Forecast", flush=True)

    df_pv_forecast = process_pv_forecast_data(pv_forecast)
    df_merged = merge_dataframes(df_load_forecast, df_pv_forecast)

    flex_price = False
    energy_price = 0.14  # 14 ct/kWh
    df = perform_calculations(df_merged, flex_price, energy_price)

    print("[*] Drawing Graphs", flush=True)
    draw_graph(df)
    surplus_times, total_savings_percentage, total_power_kwh, total_solar_kwh = output_results(df)

    return jsonify({'surplus times': surplus_times, 
                    "Total Savings (%)": total_savings_percentage,
                    "Total Predicted Energy Consumption (kWh)" : total_power_kwh,
                    "Total Predicted Solar Energy Generation (kWh)" : total_solar_kwh
                    })


# Load PV forecast data
def load_pv_forecast_data():
    with open("data/solar_prediction.json") as f:
        pv_data = json.load(f)
    return pv_data


# Load load forecast data
def load_load_forecast_data():
    with open("data/load_response.json") as f:
        load_data = json.load(f)
    return load_data


# Process load forecast data
def process_load_forecast_data(load_data):
    quantiles_data = load_data['quantiles']
    df_load_forecast = pd.DataFrame(quantiles_data)
    df_load_forecast.index = pd.to_datetime(df_load_forecast.index, unit='ms')
    df_load_forecast["time"] = pd.to_datetime(df_load_forecast.index, unit='ms')
    df_load_forecast['hour_load'] = df_load_forecast.index.hour
    return df_load_forecast


# Load form data for PV
def load_pv_form_data():
    with open("data/form_data.json") as f:
        pv_data = json.load(f)
    return pv_data


# Process PV forecast data
def process_pv_forecast_data(pv_forecast):
    df_pv_forecast = pd.DataFrame(pv_forecast["result"])
    df_pv_forecast.index = pd.to_datetime(df_pv_forecast.index)
    df_pv_forecast = df_pv_forecast.drop(columns=["watt_hours_day"])
    df_pv_forecast = df_pv_forecast.dropna()
    first_day = df_pv_forecast.index[0].date()
    df_pv_forecast = df_pv_forecast[df_pv_forecast.index.date == first_day]
    df_pv_forecast['hour_pv'] = df_pv_forecast.index.hour
    return df_pv_forecast


# Merge load and PV dataframes
def merge_dataframes(df_load_forecast, df_pv_forecast):
    df_merged = pd.merge(
        df_load_forecast,
        df_pv_forecast,
        left_on='hour_load',
        right_on='hour_pv',
        how='left'
    )
    df_merged['watts'].fillna(0, inplace=True)
    df_merged['watt_hours_period'].fillna(0, inplace=True)
    df_merged['watt_hours'].fillna(0, inplace=True)
    df_merged.drop(columns=['hour_pv'], inplace=True)
    df_merged.index = pd.to_datetime(df_merged["time"])
    return df_merged


# Perform calculations
def perform_calculations(df, flex_price=False, energy_price=0.14):
    df['power_kwh'] = df['power_0.5'] / 1000  # Convert from Watts to kWh
    df['solar_kwh'] = df['watt_hours_period'] / 1000  # Convert from watt-hours to kWh
    df['consumption_solar'] = df[['power_kwh', 'solar_kwh']].min(axis=1)
    df['consumption_grid'] = df['power_kwh'] - df['consumption_solar']
    df['consumption_grid'] = df['consumption_grid'].clip(lower=0)

    if flex_price:
        df['cost_grid'] = df['consumption_grid'] * df["total_price"]
    else:
        df['cost_grid'] = df['consumption_grid'] * energy_price

    return df


# Output results
def output_results(df):
    total_costs = df['cost_grid'].sum()
    surplus_times = df[df['consumption_grid'] == 0]['time'].tolist()
    surplus_times = [ts.strftime('%H:%M') for ts in surplus_times]

    df["energy_saved_percentage"] = df["solar_kwh"] / df["power_kwh"] * 100

    total_power_kwh = df["power_kwh"].sum()
    total_solar_kwh = df["solar_kwh"].sum()
    total_savings_percentage = total_solar_kwh / total_power_kwh * 100

    return surplus_times, total_savings_percentage, total_power_kwh, total_solar_kwh


# Draw graph
def draw_graph(df):
    fig = go.Figure()
    start_times = []
    end_times = []
    consumption_grid_zero = (df['consumption_grid'] == 0)

    previous_value = False
    for i in range(len(consumption_grid_zero)):
        current_value = consumption_grid_zero.iloc[i]
        if not previous_value and current_value:
            start_times.append(df.index[i])
        if previous_value and not current_value:
            end_times.append(df.index[i])
        previous_value = current_value

    if previous_value:
        end_times.append(df.index[-1])

    for start in start_times:
        fig.add_vline(x=start, line=dict(color='green', dash='dot'), opacity=0.5)

    for end in end_times:
        fig.add_vline(x=end, line=dict(color='green', dash='dot'), opacity=0.5)

    fig.add_trace(go.Scatter(x=df.index, y=df['power_kwh'], mode='lines', name='power_kwh', line=dict(color='blue')))
    fig.add_trace(go.Scatter(x=df.index, y=df['solar_kwh'], mode='lines', name='solar_kwh', line=dict(color='red')))
    fig.add_trace(go.Scatter(x=df.index, y=df['consumption_solar'], mode='lines', name='consumption_solar', fill='tonexty', line=dict(width=0.5, color='rgb(184, 247, 212)')))
    fig.add_trace(go.Scatter(x=df.index, y=df['consumption_grid'], mode='lines', name='consumption_grid', line=dict(color='purple')))

    fig.update_layout(xaxis_title="Time", yaxis_title="Power (Watts)")
    fig.write_html("templates/efp_prediction.html")


# Fetch load forecast from external service
def get_load_forecast(json_data):
    url = 'http://load-forecast:8000/forecast'
    headers = {'Content-Type': 'application/json'}

    response = requests.post(url, headers=headers, json=json_data)
    if response.status_code == 200:
        response_data = response.json()
        with open('data/load_response.json', 'w') as json_file:
            json.dump(response_data, json_file, indent=4)
    else:
        print(f"Error: Status Code {response.status_code}")


# Fetch PV forecast from external service
def get_pv_forecast(lat, lon, dec, az, kwp):
    url = f"https://api.forecast.solar/estimate/{lat}/{lon}/{dec}/{az}/{kwp}"
    response = requests.get(url)

    if response.status_code == 200:
        data = response.json()
        with open('data/solar_prediction.json', 'w') as json_file:
            json.dump(data, json_file, indent=4)
    else:
        print(f"Request error: Status Code {response.status_code}")


if __name__ == '__main__':
    if not os.path.exists(DATA_FOLDER):
        os.makedirs(DATA_FOLDER)
    app.run(host='0.0.0.0', port=5000, debug=True)
