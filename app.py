from flask import Flask, request, jsonify, send_file, send_from_directory, make_response
import os
import json
import csv
from datetime import datetime, timedelta
from io import BytesIO
import pandas as pd  # Requiere: pip install pandas openpyxl

app = Flask(__name__, static_folder="static")

# 📁 Configuración
DATA_DIR = 'DATA'
os.makedirs(DATA_DIR, exist_ok=True)

# 💾 Guardar en CSV histórico
def append_to_historic_csv(data):
    csv_path = os.path.join(DATA_DIR, "historico_meteo.csv")
    file_exists = os.path.isfile(csv_path)

    try:
        with open(csv_path, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow([
                    "fecha_hora", "cuenca", "servicio",
                    "temp", "rain", "rain24h",
                    "factor_temp", "factor_rain", "factor_rain24h"
                ])

            timestamp = data.get("timestamp")
            dt = datetime.fromisoformat(timestamp)
            fecha_hora = dt.strftime("%d/%m %H:%M")

            correction_factors = data.get("correctionFactors", {})

            for cuenca in ["alta", "media", "baja"]:
                cuenca_data = data.get("historicalData", {}).get(cuenca, {})
                factors = correction_factors.get(cuenca, {"temp": "", "rain": "", "rain24h": ""})

                for servicio in ["openmeteo", "wunderground", "corrected"]:
                    for punto in cuenca_data.get(servicio, []):
                        row = [
                            fecha_hora,
                            cuenca,
                            servicio,
                            punto.get("temp", "N/D"),
                            punto.get("rain", "N/D"),
                            punto.get("rain24h", "N/D"),
                        ]

                        if servicio == "corrected":
                            row += [
                                factors.get("temp", ""),
                                factors.get("rain", ""),
                                factors.get("rain24h", "")
                            ]
                        else:
                            row += ["", "", ""]

                        writer.writerow(row)
    except Exception as e:
        print(f"Error escribiendo en CSV histórico: {e}")

# 💾 Guardar datos diarios
def save_data(data):
    try:
        timestamp = data.get('timestamp')
        if not timestamp:
            return {'success': False, 'message': 'Falta el campo timestamp'}

        date = datetime.fromisoformat(timestamp)
        filename = f"meteo_{date.year}-{date.month:02d}-{date.day:02d}.json"
        filepath = os.path.join(DATA_DIR, filename)

        existing = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                existing = json.load(f)

        existing.append(data)

        with open(filepath, 'w', encoding='utf-8') as f:
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
            'alta': {'temp': 0, 'rain': 0, 'rain24h': 0},
            'media': {'temp': 0, 'rain': 0, 'rain24h': 0},
            'baja': {'temp': 0, 'rain': 0, 'rain24h': 0}
        }

        for filename in os.listdir(DATA_DIR):
            if filename.startswith('meteo_') and filename.endswith('.json'):
                with open(os.path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
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

        output = ["Fecha,Hora,Cuenca,Servicio,Temperatura,Lluvia Hoy,Lluvia 24h,Factor Temp,Factor Lluvia,Factor Lluvia24h"]

        for filename in os.listdir(DATA_DIR):
            if filename.startswith('meteo_') and filename.endswith('.json'):
                file_date = datetime.strptime(filename[6:16], '%Y-%m-%d')
                if file_date.date() >= cutoff.date():
                    with open(os.path.join(DATA_DIR, filename), 'r', encoding='utf-8') as f:
                        day_data = json.load(f)
                        for entry in day_data:
                            entry_date = datetime.fromisoformat(entry['timestamp'])
                            if entry_date >= cutoff:
                                for cuenca in ['alta', 'media', 'baja']:
                                    if cuenca in entry.get('historicalData', {}):
                                        factors = entry.get('correctionFactors', {}).get(cuenca, {})
                                        for service in ['openmeteo', 'wunderground', 'corrected']:
                                            for data_point in entry['historicalData'][cuenca].get(service, []):
                                                ts = data_point.get('timestamp')
                                                if not ts:
                                                    continue
                                                date = datetime.fromisoformat(ts)
                                                row = [
                                                    date.strftime('%d/%m/%Y'),
                                                    date.strftime('%H:%M'),
                                                    cuenca,
                                                    service,
                                                    str(data_point.get('temp', 'N/D')),
                                                    str(data_point.get('rain', 'N/D')),
                                                    str(data_point.get('rain24h', 'N/D')),
                                                    str(factors.get('temp', 0)) if service == 'corrected' else '',
                                                    str(factors.get('rain', 0)) if service == 'corrected' else '',
                                                    str(factors.get('rain24h', 0)) if service == 'corrected' else ''
                                                ]
                                                output.append(','.join(row))

        csv_content = '\n'.join(output).encode('utf-8')
        return BytesIO(csv_content)
    except Exception as e:
        return BytesIO(f"Error generando reporte: {str(e)}".encode('utf-8'))

# 🔡 Conversión ASCII a texto
def ascii_to_text(ascii_string):
    ascii_values = [int(x) for x in ascii_string.strip().split(',')]
    return ''.join(chr(x) for x in ascii_values)

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
    return jsonify(load_data())

@app.route("/report", methods=["GET"])
def report():
    range_param = request.args.get("range", "today")
    csv_file = generate_report(range_param)
    response = make_response(csv_file.getvalue())
    response.headers["Content-Disposition"] = f"attachment; filename=reporte_{range_param}.csv"
    response.headers["Content-Type"] = "text/csv"
    return response

@app.route("/descargar-historico")
def descargar_historico():
    path = os.path.join(DATA_DIR, "historico_meteo.csv")
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        return "Archivo no encontrado", 404

@app.route("/ascii-to-excel", methods=["POST"])
def ascii_to_excel():
    try:
        ascii_data = request.data.decode('utf-8')
        lines = ascii_data.strip().split('\n')
        decoded_rows = [ascii_to_text(line).split(',') for line in lines]

        if not decoded_rows:
            return jsonify({'success': False, 'message': 'No se encontraron datos'})

        headers = decoded_rows[0]
        data = decoded_rows[1:]

        df = pd.DataFrame(data, columns=headers)

        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False)

        output.seek(0)
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name='datos_convertidos.xlsx'
        )
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

# 🚀 Ejecutar servidor
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
