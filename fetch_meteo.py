import requests
import csv
import os
from datetime import datetime

# 📁 Configuración de carpeta de datos
DATA_DIR = os.path.join(os.path.dirname(__file__), "DATA")
os.makedirs(DATA_DIR, exist_ok=True)
CSV_PATH = os.path.join(DATA_DIR, "historico_meteo.csv")

# 🌎 Configuración de cuencas
cuencas = {
    "alta": {"name": "Pilar", "lat": -34.455, "lon": -58.859, "station": "IPILAR8"},
    "media": {"name": "Maschwitz", "lat": -34.386, "lon": -58.767, "station": "IINGEN19"},
    "baja": {"name": "Escobar", "lat": -34.336, "lon": -58.715, "station": "IINGEN39"}
}

# 🔑 API de Wunderground
WUNDERGROUND_API_KEY = "6532d6454b8aa370768e63d6ba5a832e"

# 🌤️ Consulta Open-Meteo
def fetch_openmeteo(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&hourly=precipitation&current=temperature_2m,precipitation&timezone=auto"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        return {
            "temp": data["current"]["temperature_2m"],
            "rain": data["current"]["precipitation"],
            "rain24h": round(sum(data["hourly"]["precipitation"][:24]), 1)
        }
    except Exception as e:
        print(f"[OpenMeteo] Error: {e}")
        return {"temp": None, "rain": None, "rain24h": None}

# 🌧️ Consulta Wunderground
def fetch_wunderground(station_id):
    url = f"https://api.weather.com/v2/pws/observations/current?stationId={station_id}&format=json&units=m&apiKey={WUNDERGROUND_API_KEY}"
    try:
        r = requests.get(url, timeout=5)
        r.raise_for_status()
        data = r.json()
        obs = data["observations"][0]["metric"]
        return {
            "temp": obs["temp"],
            "rain": obs.get("precipTotal", 0),
            "rain24h": round(obs.get("precipRate", 0) * 24, 1)
        }
    except Exception as e:
        print(f"[Wunderground] Error: {e}")
        return {"temp": None, "rain": None, "rain24h": None}

# 🧠 Función para usar desde Flask
def fetch_and_process_data():
    now = datetime.utcnow().isoformat()
    data = {
        "timestamp": now,
        "historicalData": {"alta": {}, "media": {}, "baja": {}},
        "correctionFactors": {
            "alta": {"temp": 0.0, "rain": 0.0, "rain24h": 0.0},
            "media": {"temp": 0.0, "rain": 0.0, "rain24h": 0.0},
            "baja": {"temp": 0.0, "rain": 0.0, "rain24h": 0.0}
        }
    }

    for key, c in cuencas.items():
        om = fetch_openmeteo(c["lat"], c["lon"])
        wg = fetch_wunderground(c["station"])

        data["historicalData"][key]["openmeteo"] = [{"timestamp": now, **om}]
        data["historicalData"][key]["wunderground"] = [{"timestamp": now, **wg}]

        if all(v is not None for v in om.values()) and all(v is not None for v in wg.values()):
            corrected = {
                "timestamp": now,
                "temp": round((om["temp"] + wg["temp"]) / 2, 2),
                "rain": round((om["rain"] + wg["rain"]) / 2, 2),
                "rain24h": round((om["rain24h"] + wg["rain24h"]) / 2, 2)
            }
            data["historicalData"][key]["corrected"] = [corrected]

            data["correctionFactors"][key] = {
                "temp": round(corrected["temp"] - om["temp"], 2),
                "rain": round(corrected["rain"] - om["rain"], 2),
                "rain24h": round(corrected["rain24h"] - om["rain24h"], 2)
            }
        else:
            data["historicalData"][key]["corrected"] = []

    return data

# 🧪 Ejecución directa (opcional)
if __name__ == "__main__":
    result = fetch_and_process_data()
    print(json.dumps(result, indent=2))
