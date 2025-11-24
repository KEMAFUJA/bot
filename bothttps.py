import requests
from flask import Flask, request, Response, render_template
import json
import os
import math

TOKEN = "8419395221:AAG_aNghJPVpKcS0a69_CDVMBzhNPSriw3M"
BASE_URL = f"https://api.telegram.org/bot{TOKEN}"

app = Flask(__name__)

CLIENT_FILE = "cliente.json"
SUCURSALES_FILE = "sucursal.json"
DELIVERY_FILE = "delivery.json"

# UTILIDADES

def cargar_json(path):
    if not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def guardar_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

def telegram_send(method: str, payload: dict):
    url = f"{BASE_URL}/{method}"
    try:
        resp = requests.post(url, json=payload)
        print("Telegram response:", resp.status_code, resp.text)
        return resp
    except Exception as e:
        print("Error enviando mensaje a Telegram:", e)

def distancia(lat1, lon1, lat2, lon2):
    # Fórmula Haversine
    R = 6371
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2)**2
    return 2 * R * math.asin(math.sqrt(a))

# LÓGICA DE NEGOCIO

def sucursal_mas_cercana(lat_user, lon_user):
    sucursales = cargar_json(SUCURSALES_FILE)
    mejor = None
    min_dist = float("inf")

    for s_key, s in sucursales.items():
        dist = distancia(lat_user, lon_user, s["lat"], s["lon"])
        if dist < min_dist:
            min_dist = dist
            mejor = s

    return mejor, min_dist

def delivery_mas_cercano(lat_suc, lon_suc):
    deliverys = cargar_json(DELIVERY_FILE)
    mejor = None
    min_dist = float("inf")

    for d_key, d in deliverys.items():
        if not d["disponible"]:
            continue
        dist = distancia(lat_suc, lon_suc, d["lat"], d["lon"])
        if dist < min_dist:
            min_dist = dist
            mejor = d

    return mejor, min_dist

def guardar_cliente(chat_id, nombre):
    clientes = cargar_json(CLIENT_FILE, default=[])
    # Asegurarse que clientes es lista
    if not isinstance(clientes, list):
        clientes = []
    if not any(c.get("ID") == str(chat_id) for c in clientes):
        clientes.append({"ID": str(chat_id), "NOMBRE": nombre})
        guardar_json(CLIENT_FILE, clientes)


# RUTAS  

@app.route("/", methods=["GET"])
def index():
    return render_template("index.html")

@app.route("/web", methods=["GET"])
def web():
    return render_template("index.html")

@app.route("/enviar", methods=["POST"])
def enviar_mensaje():
    data = request.get_json(force=True)
    mensaje = data.get("mensaje")
    chat_id = data.get("chat_id")

    if chat_id and mensaje.strip():
        # Enviar pedido
        telegram_send("sendMessage", {
            "chat_id": chat_id,
            "text": f"Tu pedido fue enviado:\n\n{mensaje}"
        })

        # PEDIR UBICACIÓN
        telegram_send("sendMessage", {
            "chat_id": chat_id,
            "text": "Ahora envíame tu ubicación para asignarte el delivery 🚴‍♂️",
            "reply_markup": {
                "keyboard": [[{"text": "📍 ENVIAR UBICACIÓN", "request_location": True}]],
                "resize_keyboard": True,
                "one_time_keyboard": True
            }
        })

        return f"Pedido enviado al usuario {chat_id}."
    else:
        return "Error: falta mensaje o chat_id."

@app.route("/webhook", methods=["POST"])
def webhook():
    update = request.get_json(force=True)
    print(json.dumps(update, indent=2))

    if "message" in update:
        msg = update["message"]
        chat_id = msg["chat"]["id"]
        nombre = msg["chat"].get("first_name", "Cliente")

        guardar_cliente(chat_id, nombre)

        #  Cuando el usuario envía su UBICACIÓN 
        if "location" in msg:
            lat = msg["location"]["latitude"]
            lon = msg["location"]["longitude"]

            sucursal, dist_sucursal = sucursal_mas_cercana(lat, lon)
            delivery, dist_delivery = delivery_mas_cercano(sucursal["lat"], sucursal["lon"])

            if not delivery:
                telegram_send("sendMessage", {
                    "chat_id": chat_id,
                    "text": "Lo siento, no hay deliverys disponibles 😥"
                })
                return Response("ok", 200)

            # Enviar resultado al cliente
            texto = (
                f"🏪 *Sucursal asignada:* {sucursal['nombre']}\n"
                f"📍 Distancia a ti: {dist_sucursal:.2f} km\n\n"
                f"🚴‍♂️ *Delivery:* {delivery['nombre']}\n"
                f"📏 Distancia a sucursal: {dist_delivery:.2f} km\n"
            )

            telegram_send("sendMessage", {
                "chat_id": chat_id,
                "text": texto,
                "parse_mode": "Markdown"
            })

        #  START 
        if "text" in msg and msg["text"].lower() == "/start":
            url_html = "https://celeste-epigastric-dortha.ngrok-free.dev/web"
            telegram_send("sendMessage", {
                "chat_id": chat_id,
                "text": f"Hola {nombre} 👋\nHaz clic abajo para hacer tu pedido:",
                "reply_markup": {
                    "inline_keyboard": [
                        [{
                            "text": "🛒 Abrir formulario",
                            "web_app": {"url": url_html}
                        }]
                        
                    ]
                }
            })

    return Response("ok", status=200)

# RUN
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
