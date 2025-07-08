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
HISTORICO_CSV = "historico_meteo.csv"  # Nombre centralizado del archivo

# 💾 Guardar en CSV histórico
def append_to_historic_csv(data):
    csv_path = os.path.join(DATA_DIR, HISTORICO_CSV)

    try:
        timestamp = data.get("timestamp")
        dt = datetime.fromisoformat(timestamp)
        fecha = dt.strftime("%Y-%m-%d")
        hora = dt.strftime("%H:%M")

        filas = []

        # Factores de corrección primero
        correction_factors = data.get("correctionFactors", {})
        for cuenca in ["alta", "media", "baja"]:
            factores = correction_factors.get(cuenca, {"temp": "", "rain": "", "rain24h": ""})
            filas.append([
                fecha, hora, cuenca, "Factor de Corrección",
                "", "", "",
                factores.get("temp", ""),
                factores.get("rain", ""),
                factores.get("rain24h", "")
            ])

        # Luego datos meteorológicos
        for cuenca in ["alta", "media", "baja"]:
            cuenca_data = data.get("historicalData", {}).get(cuenca, {})
            for servicio in ["openmeteo", "wunderground", "corrected"]:
                for punto in cuenca_data.get(servicio, []):
                    filas.append([
                        fecha, hora, cuenca, servicio,
                        punto.get("temp", ""),
                        punto.get("rain", ""),
                        punto.get("rain24h", ""),
                        "", "", ""
                    ])

        # Escribir archivo completo (sobrescribe)
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                "Fecha", "Hora", "Cuenca", "Servicio", "Temperatura",
                "Lluvia Hoy", "Lluvia 24h", "Factor Temp", "Factor Lluvia", "Factor Total"
            ])
            writer.writerows(filas)

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

        # Guardar datos diarios en archivo JSON
        existing = []
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                existing = json.load(f)

        existing.append(data)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(existing, f, indent=2)

        # Agregar datos al CSV histórico (sin sobrescribir)
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
    path = os.path.join(DATA_DIR, HISTORICO_CSV)
    if os.path.exists(path):
        return send_file(path, as_attachment=True)
    else:
        return "Archivo no encontrado", 404

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

# ✅ Vinculación real con fetch_meteo
from fetch_meteo import fetch_and_process_data

@app.route("/post-datos-desde-google", methods=["POST"])
def post_datos_desde_google():
    try:
        data = fetch_and_process_data()
        save_data(data)
        return jsonify({"success": True, "message": "Datos reales guardados correctamente"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})

# ==============================================
# 🔄 ENDPOINTS PARA ALMACENAMIENTO EXTERNO
# ==============================================

@app.route("/backup-historico", methods=["GET"])
def backup_historico():
    try:
        csv_path = os.path.join(DATA_DIR, HISTORICO_CSV)
        if not os.path.exists(csv_path):
            return jsonify({"success": False, "message": "Archivo histórico no encontrado"}), 404
        if os.path.getsize(csv_path) == 0:
            return jsonify({"success": False, "message": "Archivo histórico vacío"}), 400
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        return send_file(
            csv_path,
            as_attachment=True,
            download_name=f"meteo_backup_{timestamp}.csv",
            mimetype="text/csv"
        )
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500

@app.route("/verificar-backup", methods=["GET"])
def verificar_backup():
    csv_path = os.path.join(DATA_DIR, HISTORICO_CSV)
    if not os.path.exists(csv_path):
        return jsonify({
            "success": False,
            "exists": False,
            "message": "Archivo histórico no encontrado"
        }), 404
    stats = {
        "success": True,
        "exists": True,
        "size_kb": round(os.path.getsize(csv_path) / 1024, 2),
        "last_modified": datetime.fromtimestamp(
            os.path.getmtime(csv_path)
        ).isoformat(),
        "lines": sum(1 for _ in open(csv_path, 'r', encoding='utf-8'))
    }
    return jsonify(stats)

# 🚀 Ejecutar servidor
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
