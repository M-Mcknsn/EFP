
# Energy Forecast Planner

This service combines energy load forecasts with solar generation forecasts to identify hours of energy surplus, enabling better planning for sustainable energy consumption.




## Load Forecast
To predict the energy consumption for the upcoming day, the load forecasting service from the **Foresight Next Project**, developed by the **German Research Center for Artificial Intelligence (DFKI)**, is utilized. This service analyzes historical load data to generate load forecasts. Further details can be found here:
- [foresight-next ai services](https://github.com/connected-intelligent-systems/foresight-next-ai-services/tree/main)
- [load-forecasting-service](https://github.com/connected-intelligent-systems/foresight-next-ai-services/blob/main/load-forecasting/README.md)


## Forecast.Solar
The **Forecast.Solar API** is employed to predict the expected solar energy generation at an hourly resolution a given day. This API provides detailed solar energy forecasts based on geographical and technical parameters. More information can be found here:
- [Forecast.Solar Documentation](https://doc.forecast.solar/start)


## System Architecture

![EFPArchitecture](https://github.com/user-attachments/assets/f80b8109-088c-417c-9f42-6d2db1c33870)



The web application processes input data such as historical load data and solar plant configurations to obtain solar energy forecasts using the Forecast.Solar API. The application, based on Flask and running in Docker containers, combines solar and load forecasts to predict surpluses or deficits in solar production. An additional load forecast service from DFKI provides load forecasts. The results are provided as interactive diagrams and JSON data.

## Setup Instructions

To start the services using Docker Compose, run the following command:

```
docker-compose up
```

### Configuring Photovoltaic (PV) Systems

Solar energy predictions are generated based on the configuration of the photovoltaic (PV) system. This configuration can be submitted via the following form:

- **URL**: [http://localhost:5000/efp](http://localhost:5000/efp)

The following parameters are required, as derived from the [Forecast.Solar documentation](https://doc.forecast.solar/api:estimate):

- `lat`: Latitude of the location, ranging from -90 (South) to 90 (North), handled with a precision of 0.0001 (~10 meters).
- `lon`: Longitude of the location, ranging from -180 (West) to 180 (East), handled with a precision of 0.0001 (~10 meters).
- `dec`: Plane declination, ranging from 0 (horizontal) to 90 (vertical), in relation to the Earth's surface (integer).
- `az`: Plane azimuth, ranging from -180 to 180 (with -180 and 180 representing North, -90 representing East, and 0 representing South).
- `kwp`: Installed power of the PV modules, measured in kilowatts (float).

Alternatively, the following cURL command can be used to set the PV configuration:
```
curl localhost:5000/efp/pv-config/<lat>/<lon>/<dec>/<az>/<kwp>
```


### Prediction Generation

To generate energy consumption and solar energy production forecasts, the system requires a minimum of 8 days of historical load data. These data should be provided in the form of UNIX timestamps (representing time) and power values (in watts).

A [sample dataset](https://github.com/connected-intelligent-systems/foresight-next-ai-services/tree/main/load-forecasting/sample_data) provided by DFKI will be used in this demo.


The following cURL command can be used to submit the load data and obtain predictions:

```
curl -X POST http://localhost:5000/efp/predict -F "file=@sample_data/example_request.json"
```

Alternatively, the predictions can be generated programmatically using Python:

```
import requests

url = "http://localhost:5000/efp/predict"

with open('sample_data/example_request.json', 'rb') as file:

    files = {'file': file} 

    response = requests.post(url, files=files)

    if response.status_code == 200:
        print("Response:")
        print(response.json())  
    else:
        print(f"Error: {response.status_code}")
        print(response.text)
```

Upon successful submission, the system will return a response similar to the following:
```
{
    "Total Predicted Energy Consumption (kWh)": 10.122631806982001,
    "Total Predicted Solar Energy Generation (kWh)": 13.775,
    "Total Savings (%)": 136.08121151357898,
    "surplus times": ["09:00", "10:00", "11:00", "12:00", "13:00", "14:00", "15:00", "16:00", "17:00"]
}
```

### Displaying Diagrams
Based on the generated predictions, a visual representation in the form of a diagram is available, providing a clearer understanding of energy usage and solar production patterns.

- **URL**: [http://localhost:5000/efp/display](http://localhost:5000/efp/display)


![DiagrammExample](https://github.com/user-attachments/assets/b3100726-ae15-442e-a81d-ee8f6ec28b1a)







