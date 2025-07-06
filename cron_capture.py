import urllib.request

# URL pública de tu app Flask en Render
URL = "https://test-meteoweb.onrender.com/update"

def main():
    try:
        with urllib.request.urlopen(URL) as response:
            status = response.status
            body = response.read().decode('utf-8')
            print(f"Respuesta del servidor: {status}")
            print(body)
    except Exception as e:
        print("Error al contactar la app:", e)

if __name__ == "__main__":
    main()
