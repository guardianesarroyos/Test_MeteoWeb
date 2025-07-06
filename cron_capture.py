import requests

# URL pública de tu app Flask en Render
URL = "https://test-meteoweb.onrender.com/update"

try:
    response = requests.get(URL)
    print("Respuesta del servidor:", response.status_code)
    print(response.text)
except Exception as e:
    print("Error al contactar la app:", e)
