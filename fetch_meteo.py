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

# 🌤️ Función para consultar Open-Meteo
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

# 🌧️ Función para consultar Wunderground
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

# 💾 Guardar en CSV
def append_csv(filename, fila):
    file_exists = os.path.isfile(filename)
    with open(filename, "a", newline="") as f:
        writer = csv.writer(f)
        if not file_exists:
            writer.writerow(["timestamp", "cuenca", "servicio", "temp", "rain", "rain24h"])
        writer.writerow(fila)

# 🚀 Ejecución principal
def main():
    now = datetime.utcnow().isoformat()
    for key, c in cuencas.items():
        om = fetch_openmeteo(c["lat"], c["lon"])
        wg = fetch_wunderground(c["station"])

        if all(v is not None for v in om.values()):
            append_csv(CSV_PATH, [now, key, "openmeteo", om["temp"], om["rain"], om["rain24h"]])
        else:
            print(f"[{key}] OpenMeteo incompleto: {om}")

        if all(v is not None for v in wg.values()):
            append_csv(CSV_PATH, [now, key, "wunderground", wg["temp"], wg["rain"], wg["rain24h"]])
        else:
            print(f"[{key}] Wunderground incompleto: {wg}")

if __name__ == "__main__":
    main()
