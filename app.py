from flask import Flask, request, jsonify, send_file, make_response
import os
import json
import csv
from datetime import datetime, timedelta
from io import BytesIO

app = Flask(__name__)

# 📁 Configuración
DATA_DIR = 'DATA'
os.makedirs(DATA_DIR, exist_ok=True)

# 💾 Guardar en CSV histórico
def append_to_historic_csv(data):
    csv_path = os.path.join(DATA_DIR, "historico_meteo.csv")
    file_exists = os.path.isfile(csv_path)
    
    try:
        with open(csv_path, "a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "cuenca", "servicio", "temp", "rain", "rain24h"])
            
            for cuenca in ["alta", "media", "baja"]:
                cuenca_data = data.get("historicalData", {}).get(cuenca, {})
                for servicio in ["openmeteo", "wunderground"]:
                    for punto in cuenca_data.get(servicio, []):
                        writer.writerow([
                            punto.get("timestamp", data.get("timestamp")),
                            cuenca,
                            servicio,
                            punto.get("temp", "N/D"),
                            punto.get("rain", "N/D"),
                            punto.get("rain24h", "N/D")
                        ])
    except Exception as e:
        print(f"Error escribiendo en CSV histórico: {e}")

# 💾 Guardar datos diarios
def save_data(data):
    try:
        date = datetime.fromisoformat(data['timestamp'])
        filename = f"meteo_{date.year}-{date.month:02d}-{date.day:02d}.json"
        filepath = os.path.join(DATA_DIR, filename)

        existing = []
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                existing = json.load(f)

        existing.append(data)

        with open(filepath, 'w') as f:
            json.dump(existing, f, indent=2)

        append_to_historic_csv(data)
        return {'success': True}
    except Exception as e:
        return {'success': False, 'message': str(e)}

# 📤 Cargar datos históricos
def load_data():
    try:
        historical_data = {
            'alta': {'openmeteo': [], 'wunderground': [], 'corrected': []},
            'media': {'openmeteo': [], 'wunderground': [], 'corrected': []},
            'baja': {'openmeteo': [], 'wunderground': [], 'corrected': []}
        }
        correction_factors = {
            'alta': {'temp': 0, 'rain': 0, 'rain24h': 0, 'count': 0},
            'media': {'temp': 0, 'rain': 0, 'rain24h': 0, 'count': 0},
            'baja': {'temp': 0, 'rain': 0, 'rain24h': 0, 'count': 0}
        }

        for filename in os.listdir(DATA_DIR):
            if filename.startswith('meteo_') and filename.endswith('.json'):
                with open(os.path.join(DATA_DIR, filename), 'r') as f:
                    day_data = json.load(f)
                    for entry in day_data:
                        for cuenca in ['alta', 'media', 'baja']:
                            if cuenca in entry.get('historicalData', {}):
                                for service in ['openmeteo', 'wunderground', 'corrected']:
                                    if service in entry['historicalData'][cuenca]:
                                        historical_data[cuenca][service].extend(entry['historicalData'][cuenca][service])

                            if cuenca in entry.get('correctionFactors', {}):
                                for factor in ['temp', 'rain', 'rain24h']:
                                    if factor in entry['correctionFactors'][cuenca]:
                                        correction_factors[cuenca][factor] = entry['correctionFactors'][cuenca][factor]

        return {'success': True, 'historicalData': historical_data, 'correctionFactors': correction_factors}
    except Exception as e:
        return {'success': False, 'message': str(e)}

# 📄 Generar reporte CSV
def generate_report(range_str):
    try:
        now = datetime.now()
        if range_str == 'last-hour':
            cutoff = now - timedelta(hours=1)
        elif range_str == 'today':
            cutoff = now.replace(hour=0, minute=0, second=0, microsecond=0)
        elif range_str == 'last-week':
            cutoff = now - timedelta(days=7)
        elif range_str == 'last-month':
            cutoff = now - timedelta(days=30)
        elif range_str == 'last-3days':
            cutoff = now - timedelta(days=3)
        else:
            cutoff = now - timedelta(days=365)

        output = []
        output.append("Fecha,Hora,Cuenca,Servicio,Temperatura,Lluvia Hoy,Lluvia 24h,Factor Temp,Factor Lluvia,Factor Lluvia24h")

        for filename in os.listdir(DATA_DIR):
            if filename.startswith('meteo_') and filename.endswith('.json'):
                file_date = datetime.strptime(filename[6:16], '%Y-%m-%d')
                if file_date.date() >= cutoff.date():
                    with open(os.path.join(DATA_DIR, filename), 'r') as f:
                        day_data = json.load(f)
                        for entry in day_data:
                            entry_date = datetime.fromisoformat(entry['timestamp'])
                            if entry_date >= cutoff:
                                for cuenca in ['alta', 'media', 'baja']:
                                    if cuenca in entry.get('historicalData', {}):
                                        factors = entry.get('correctionFactors', {}).get(cuenca, {})
                                        for service in ['openmeteo', 'wunderground', 'corrected']:
                                            if service in entry['historicalData'][cuenca]:
                                                for data_point in entry['historicalData'][cuenca][service]:
                                                    date = datetime.fromisoformat(data_point['timestamp'])
                                                    fecha_str = date.strftime('%d/%m/%Y')
                                                    hora_str = date.strftime('%H:%M')

                                                    row = [
                                                        fecha_str,
                                                        hora_str,
                                                        cuenca,
                                                        service,
                                                        str(data_point.get('temp', 'N/D')),
                                                        str(data_point.get('rain', 'N/D')),
                                                        str(data_point.get('rain24h', 'N/D')),
                                                        str(factors.get('temp', 0)),
                                                        str(factors.get('rain', 0)),
                                                        str(factors.get('rain24h', 0))
                                                    ]
                                                    output.append(','.join(row))

        csv_content = '\n'.join(output).encode('utf-8')
        return BytesIO(csv_content)
    except Exception as e:
        return BytesIO(f"Error generando reporte: {str(e)}".encode('utf-8'))


# 🌐 Rutas Flask

@app.route("/status", methods=["GET"])
def status():
    return jsonify({'success': True, 'status': 'online'})

@app.route("/save", methods=["POST"])
def save():
    try:
        data = request.get_json()
        result = save_data(data)
        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route("/load", methods=["GET"])
def load():
    result = load_data()
    return jsonify(result)

@app.route("/report", methods=["GET"])
def report():
    range_param = request.args.get("range", "today")
    csv_file = generate_report(range_param)
    response = make_response(csv_file.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=reporte_{range_param}.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

# 🚀 Ejecutar localmente (opcional)
@app.route("/descargar-historico")
def descargar_historico():
    path = os.path.join(DATA_DIR, "historico_meteo.csv")
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        return "Archivo no encontrado", 404

@app.route("/")
def home():
    return send_from_directory("static", "index.html")

if __name__ == "__main__":
    app.run(debug=True)
