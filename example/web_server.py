import json
import os
import requests
import csv
import io
import sqlite3
import shutil
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, send_file

# --- KONFIGURACJA ŚCIEŻEK ---
DATA_FILE = "/data/employees.json"
OPTIONS_FILE = "/data/options.json"
DB_FILE = "/data/employee_history.db"
HISTORY_FILE = "/data/history.json"

# Ścieżki do instalacji kart
SOURCE_JS_FILE = "/app/employee-card.js"
HA_WWW_DIR = "/config/www"
DEST_JS_FILE = os.path.join(HA_WWW_DIR, "employee-card.js")
CARD_URL_RESOURCE = "/local/employee-card.js"

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
TOKEN = ""
API_URL = ""

if SUPERVISOR_TOKEN:
    TOKEN = SUPERVISOR_TOKEN
    API_URL = "http://supervisor/core/api"
    # Zmieniona informacja w logu, żeby widzieć skąd startujemy
    print(">>> [API] Używam Supervizora (Adres: supervisor/core/api)", flush=True)
else:
    # Ten blok jest tylko awaryjny (jeśli w ogóle nie ma Supervisora)
    print(">>> [API] OSTRZEŻENIE: Brak Supervizora - Fallback na plik opcji.", flush=True)
    try:
        if os.path.exists(OPTIONS_FILE):
            with open(OPTIONS_FILE, 'r') as f:
                opts = json.load(f)
                TOKEN = opts.get("ha_token", "").strip()
    except: pass
    
    # Używamy adresu wewnętrznego HA, ale on jest zawodny bez Supervizora
    API_URL = "http://homeassistant:8123/api"
    
if not TOKEN:
    print("!!! [API] Błąd: Brak tokena do komunikacji z HA.", flush=True)
    
HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

app = Flask(__name__)

# --- LISTY I SŁOWNIKI POMOCNICZE ---
SUFFIXES_TO_CLEAN = [
    "_status", "_czas_pracy", 
    "_temperatura", "_wilgotnosc", "_cisnienie", 
    "_moc", "_napiecie", "_natezenie", 
    "_bateria", "_pm25", "_jasnosc"
]

GLOBAL_BLACKLIST = [
    "indicator", "light", "led", "display", "lock", "child", "physical control",     
    "filter", "life", "used time", "alarm", "error", "fault", "problem",     
    "update", "install", "version", "identify", "zidentyfikuj", "info",
    "iphone", "ipad", "phone", "mobile", "router", "gateway", "brama"      
]

PRETTY_NAMES = {
    "temperature": "Temperatura", "humidity": "Wilgotność", "pressure": "Ciśnienie",
    "power": "Moc", "energy": "Energia", "voltage": "Napięcie", "current": "Natężenie",
    "battery": "Bateria", "signal_strength": "Sygnał", "pm25": "PM 2.5", "illuminance": "Jasność",
    "connectivity": "Połączenie"
}

BLOCKED_PREFIXES = ["sensor.backup_", "sensor.sun_", "sensor.date", "sensor.time", "sensor.zone", "sensor.automation", "sensor.script", "update.", "person.", "zone.", "sun.", "todo.", "button.", "input_"]
BLOCKED_DEVICE_CLASSES = ["timestamp", "enum", "update", "date", "identify"]

# --- FUNKCJE POMOCNICZE ---
def load_json(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except: return []

def save_json(file_path, data):
    with open(file_path, 'w') as f: json.dump(data, f, indent=4)

def delete_ha_state(entity_id):
    try:
        requests.delete(f"{API_URL}/states/{entity_id}", headers=HEADERS)
    except: pass

def get_ha_state(entity_id):
    try:
        resp = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
        if resp.status_code == 200:
            state = resp.json().get("state")
            try: return str(round(float(state), 1))
            except: return state
    except: pass
    return "-"

def get_clean_sensors():
    sensors = []
    try:
        resp = requests.get(f"{API_URL}/states", headers=HEADERS)
        if resp.status_code == 200:
            all_states = resp.json()
            for entity in all_states:
                eid = entity['entity_id']
                attrs = entity.get("attributes", {})
                friendly_name = attrs.get("friendly_name", eid).lower()
                device_class = attrs.get("device_class")
                
                if not (eid.startswith(("sensor.", "binary_sensor.", "switch.", "light."))): continue
                if attrs.get("managed_by") == "employee_manager": continue
                if eid.endswith("_status") or eid.endswith("_czas_pracy"): continue
                if any(bad_word in friendly_name for bad_word in GLOBAL_BLACKLIST): continue
                if any(eid.startswith(p) for p in BLOCKED_PREFIXES): continue
                if device_class in BLOCKED_DEVICE_CLASSES: continue
                if " - " in friendly_name and "status" in friendly_name: continue 

                unit = attrs.get("unit_of_measurement", "")
                orig_friendly_name = attrs.get("friendly_name", eid)
                main_label = orig_friendly_name
                
                if device_class in PRETTY_NAMES: main_label = PRETTY_NAMES[device_class]
                elif unit == "W": main_label = "Moc"
                elif unit == "V": main_label = "Napięcie"
                elif unit == "kWh": main_label = "Energia"
                elif unit == "%": main_label = "Wilgotność"
                
                sensors.append({
                    "id": eid, 
                    "main_label": main_label, 
                    "sub_label": orig_friendly_name,
                    "unit": unit, 
                    "state": entity.get("state", "-"), 
                    "device_class": device_class
                })
            sensors.sort(key=lambda x: (x['main_label'], x['sub_label']))
    except Exception as e:
        print(f"Błąd API: {e}", flush=True)
    return sensors

def install_and_register_card():
    # 1. Ścieżki
    SOURCE = "/app/employee-card.js"
    DEST_DIR = "/config/www"
    DEST_FILE = os.path.join(DEST_DIR, "employee-card.js")
    RESOURCE_URL = "/local/employee-card.js"

    # 2. Fizyczne Kopiowanie Pliku
    try:
        if not os.path.exists(DEST_DIR):
            os.makedirs(DEST_DIR)
        
        # Sprawdź czy źródło istnieje (bo mogło nie zostać skopiowane do kontenera)
        if not os.path.exists(SOURCE):
             return False, "Błąd: Plik źródłowy employee-card.js nie istnieje w /app"

        shutil.copy2(SOURCE, DEST_FILE)
        print(f">>> SKOPIOWANO: {SOURCE} -> {DEST_FILE}", flush=True)
    except Exception as e:
        return False, f"Błąd kopiowania pliku: {str(e)}"

    # 3. Rejestracja w API
    api_url = f"{API_URL}/lovelace/resources"
    try:
        get_res = requests.get(api_url, headers=HEADERS)
        if get_res.status_code == 200:
            resources = get_res.json()
            for res in resources:
                if res['url'] == RESOURCE_URL:
                    return True, "Karta zaktualizowana!"
        
        payload = {"type": "module", "url": RESOURCE_URL}
        post_res = requests.post(api_url, headers=HEADERS, json=payload)
        
        if post_res.status_code in [200, 201]:
            return True, "Karta zarejestrowana pomyślnie!"
        else:
            return False, f"Błąd API HA ({post_res.status_code})"
    except Exception as e:
        return False, f"Błąd API: {str(e)}"

# --- ENDPOINTY FLASK ---
@app.route('/')
def index():
    return render_template('index.html', all_sensors=get_clean_sensors())

@app.route('/api/employees', methods=['GET'])
def api_get(): return jsonify(load_json(DATA_FILE))

@app.route('/api/employees', methods=['POST'])
def api_post():
    data = request.json
    emps = load_json(DATA_FILE)
    emps = [e for e in emps if e['name'] != data['name']]
    # Usuwamy grupę jeśli przyszła
    if 'group' in data: del data['group']
    emps.append(data)
    save_json(DATA_FILE, emps)
    return jsonify({"status":"ok"})

@app.route('/api/employees/<int:i>', methods=['DELETE'])
def api_del(i):
    emps = load_json(DATA_FILE)
    if 0 <= i < len(emps):
        to_delete = emps[i]
        safe_name = to_delete['name'].lower().replace(" ", "_")
        delete_ha_state(f"sensor.{safe_name}_status")
        delete_ha_state(f"sensor.{safe_name}_czas_pracy")
        for suffix in SUFFIXES_TO_CLEAN:
            delete_ha_state(f"sensor.{safe_name}{suffix}")
        del emps[i]
        save_json(DATA_FILE, emps)
    return jsonify({"status":"ok"})

@app.route('/api/monitor', methods=['GET'])
def api_monitor():
    emps = load_json(DATA_FILE)
    res = []
    for emp in emps:
        safe = emp['name'].lower().replace(" ","_")
        status = get_ha_state(f"sensor.{safe}_status") or "N/A"
        time = get_ha_state(f"sensor.{safe}_czas_pracy") or "0"
        meas = []
        for entity_id in emp.get('sensors', []):
            val = get_ha_state(entity_id)
            meas.append({"label": entity_id, "value": val, "unit": ""}) 
        res.append({"name": emp['name'], "status": status, "work_time": time, "measurements": meas})
    return jsonify(res)

@app.route('/api/install_card', methods=['POST'])
def api_install_card():
    success, msg = install_and_register_card()
    if success:
        return jsonify({"success": True, "message": msg})
    else:
        return jsonify({"success": False, "message": msg}), 500

@app.route('/api/history', methods=['GET'])
def api_history():
    return jsonify(load_json(HISTORY_FILE))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)