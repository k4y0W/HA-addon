import json
import os
import requests
import csv
import io
import sqlite3
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, send_file

# --- KONFIGURACJA ---
HARDCODED_TOKEN = ""
DATA_FILE = "/data/employees.json"
GROUPS_FILE = "/data/groups.json"
OPTIONS_FILE = "/data/options.json"
DB_FILE = "/data/employee_history.db"
HISTORY_FILE = "/data/history.json"
SOURCE_JS_FILE = "/employee-card.js"

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
USER_TOKEN_FROM_FILE = ""

try:
    with open(OPTIONS_FILE, 'r') as f:
        opts = json.load(f)
        USER_TOKEN_FROM_FILE = opts.get("ha_token", "")
except: pass

if len(HARDCODED_TOKEN) > 50:
    TOKEN = HARDCODED_TOKEN
    API_URL = "http://homeassistant:8123/api"
elif len(USER_TOKEN_FROM_FILE) > 50:
    TOKEN = USER_TOKEN_FROM_FILE
    API_URL = "http://homeassistant:8123/api"
else:
    TOKEN = SUPERVISOR_TOKEN
    API_URL = "http://supervisor/core/api"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

app = Flask(__name__)

# --- KONFIGURACJA SENSORÓW ---
SUFFIXES_TO_CLEAN = [
    "_status", "_czas_pracy", 
    "_temperatura", "_wilgotnosc", "_cisnienie", 
    "_moc", "_napiecie", "_natezenie", 
    "_bateria", "_pm25", "_jasnosc"
]
GLOBAL_BLACKLIST = [
    "indicator", "light", "led", "display",   
    "lock", "child", "physical control",     
    "filter", "life", "used time",           
    "alarm", "error", "fault", "problem",     
    "update", "install", "version",           
    "identify", "zidentyfikuj", "info",
    "iphone", "ipad", "phone", "mobile", 
    "router", "gateway", "brama"      
]

BLOCKED_KEYWORDS = [
    "App Version", "Audio Output", "BSSID", "SSID", "Connection Type", 
    "Geocoded Location", "Last Update Trigger", "Location permission", 
    "SIM 1", "SIM 2", "Storage", "Battery State", "Activity", "Focus",
    "Distance Traveled", "Floors Ascended", "Steps", "Average Active Pace"
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
        if file_path == GROUPS_FILE:
            default_groups = ["Domyślna"]
            save_json(GROUPS_FILE, default_groups)
            return default_groups
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

                if attrs.get("managed_by") == "employee_manager":
                    continue

                if eid.endswith("_status") or eid.endswith("_czas_pracy"):
                    continue

                if any(bad_word in friendly_name for bad_word in GLOBAL_BLACKLIST):
                    continue

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

def get_ha_state(entity_id):
    try:
        resp = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
        if resp.status_code == 200:
            state = resp.json().get("state")
            try: return str(round(float(state), 1))
            except: return state
    except: pass
    return "-"

def register_lovelace_resource():
    CARD_URL = "/local/employee-card.js"
    install_headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    try:
        url = f"{API_URL}/lovelace/resources"
        get_resp = requests.get(url, headers=install_headers)
        if get_resp.status_code in [401, 403, 404]: return False, "Brak uprawnień API."
        resources = get_resp.json()
        for res in resources:
            if res['url'] == CARD_URL: return True, "Zasób już istnieje!"
        payload = {"url": CARD_URL, "type": "module"}
        post_resp = requests.post(url, headers=install_headers, json=payload)
        if post_resp.status_code in [200, 201]: return True, "Dodano kartę!"
        else: return False, f"Błąd API: {post_resp.text}"
    except Exception as e: return False, str(e)

# --- ENDPOINTY FLASK ---
@app.route('/')
def index():
    return render_template('index.html', all_sensors=get_clean_sensors())

@app.route('/api/groups', methods=['GET', 'POST'])
def handle_groups():
    grps = load_json(GROUPS_FILE)
    if not grps: grps = ["Domyślna"]
    if request.method == 'POST':
        name = request.json.get('name')
        if name and name not in grps: grps.append(name)
        save_json(GROUPS_FILE, grps)
    return jsonify(grps)

@app.route('/api/groups/<name>', methods=['DELETE'])
def del_group(name):
    if name == "Domyślna": return jsonify({"error": "Nie można usunąć"}), 400
    grps = load_json(GROUPS_FILE)
    if name in grps: grps.remove(name)
    save_json(GROUPS_FILE, grps)
    emps = load_json(DATA_FILE)
    for e in emps:
        if e.get('group') == name: e['group'] = "Domyślna"
    save_json(DATA_FILE, emps)
    return jsonify({"status":"ok"})

@app.route('/api/employees', methods=['GET'])
def api_get(): return jsonify(load_json(DATA_FILE))

@app.route('/api/employees', methods=['POST'])
def api_post():
    data = request.json
    emps = load_json(DATA_FILE)
    emps = [e for e in emps if e['name'] != data['name']]
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
            try:
                r = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
                data = r.json()
                attrs = data['attributes']
                friendly_name = attrs.get('friendly_name', entity_id)
                dc = attrs.get('device_class')
                unit = attrs.get('unit_of_measurement', '')
                label = friendly_name
                if dc in PRETTY_NAMES: label = PRETTY_NAMES[dc]
                elif unit == "W": label = "Moc"
                meas.append({"label": label, "value": val, "unit": unit})
            except: pass
        res.append({"name": emp['name'], "group": emp.get('group', 'Domyślna'), "status": status, "work_time": time, "measurements": meas})
    return jsonify(res)

@app.route('/download_report')
def download_report():
    """Generuje raport CSV z bazy danych SQLite"""
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT work_date, employee_name, minutes_worked FROM work_history ORDER BY work_date DESC")
        rows = c.fetchall()
        conn.close()

        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Data", "Pracownik", "Minuty", "Godziny (ok.)"])
        
        for row in rows:
            # row[0]=Date, row[1]=Name, row[2]=Minutes
            hours = round(row[2] / 60, 2)
            cw.writerow([row[0], row[1], row[2], str(hours).replace('.', ',')])
            
        return Response(si.getvalue(), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=Raport_Historii.csv"})
    except Exception as e:
        return f"Błąd generowania raportu: {e}", 500

@app.route('/api/install_card', methods=['POST'])
def api_install_card():
    success, msg = register_lovelace_resource()
    return jsonify({"success": success, "message": msg})

@app.route('/local/employee-card.js')
def serve_card_file():
    if os.path.exists(CARD_FILE_PATH):
        return send_file(CARD_FILE_PATH, mimetype='application/javascript')
    else:
        return f"Błąd: Nie znaleziono pliku {CARD_FILE_PATH}", 404

@app.route('/api/history', methods=['GET'])
def api_history():
    return jsonify(load_json(HISTORY_FILE))
    
if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)

