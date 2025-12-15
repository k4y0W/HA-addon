import json
import os
import requests
import sqlite3
import shutil
import time
import threading
from datetime import datetime
from flask import Flask, request, jsonify, render_template, Response, send_file

# --- CONFIGURATION ---
DATA_FILE = "/data/employees.json"
STATUS_FILE = "/data/status.json"
OPTIONS_FILE = "/data/options.json"
DB_FILE = "/data/employee_history.db"
HISTORY_FILE = "/data/history.json"
HA_WWW_DIR = "/config/www"
CARD_URL_RESOURCE = "/local/employee-card.js"

# --- SMART PATH DETECTION FOR CARD FILE ---
# We check current directory, /app, and root to find the JS file
POSSIBLE_PATHS = [
    os.path.join(CURRENT_DIR, 'example', 'employee-card.js'), # 1. PRIORYTET: Folder example obok skryptu
    os.path.join(CURRENT_DIR, 'employee-card.js'),            # 2. Ten sam folder co skrypt
    '/app/example/employee-card.js',                          # 3. Pełna ścieżka w Dockerze (example)
    '/app/employee-card.js',                                  # 4. Pełna ścieżka w Dockerze (root)
    'example/employee-card.js'                                # 5. Ścieżka względna
]
SOURCE_CARD_FILE = None
for path in POSSIBLE_PATHS:
    if os.path.exists(path):
        SOURCE_CARD_FILE = path
        break

# Default fallback if not found (will cause error later but better than crash)
if not SOURCE_CARD_FILE:
    SOURCE_CARD_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'employee-card.js')

# --- API & TOKEN SETUP ---
TOKEN = ""
API_URL = ""

try:
    if os.path.exists(OPTIONS_FILE):
        with open(OPTIONS_FILE, 'r') as f:
            opts = json.load(f)
            TOKEN = opts.get("ha_token", "").strip()
except:
    pass

if len(TOKEN) > 50:
    API_URL = "http://172.30.32.1:8123/api"
    print(f">>> [INIT] MANUAL MODE: User Token. URL: {API_URL}", flush=True)
else:
    TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
    API_URL = "http://supervisor/core/api"
    print(">>> [INIT] SUPERVISOR MODE: System Token.", flush=True)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

app = Flask(__name__)

# --- UNIT MAPPING ---
UNIT_MAP = {
    "W": {"suffix": "moc", "icon": "mdi:lightning-bolt"},
    "kW": {"suffix": "moc", "icon": "mdi:lightning-bolt"},
    "V": {"suffix": "napiecie", "icon": "mdi:sine-wave"},
    "A": {"suffix": "natezenie", "icon": "mdi:current-ac"},
    "°C": {"suffix": "temperatura", "icon": "mdi:thermometer"},
    "%": {"suffix": "wilgotnosc", "icon": "mdi:water-percent"},
    "hPa": {"suffix": "cisnienie", "icon": "mdi:gauge"},
    "ug/m³": {"suffix": "pm25", "icon": "mdi:blur"},
}

MANAGED_SUFFIXES = ["_status", "_czas_pracy"]
GLOBAL_BLACKLIST = [
    "indicator", "light", "led", "display", "lock", "child", "physical control",     
    "filter", "life", "used time", "alarm", "error", "fault", "problem",     
    "update", "install", "version", "identify", "zidentyfikuj", "info",
    "iphone", "ipad", "phone", "mobile", "router", "gateway", "brama"      
]
BLOCKED_PREFIXES = ["sensor.backup_", "sensor.sun_", "sensor.date", "sensor.time", "sensor.zone", "sensor.automation", "sensor.script", "update.", "person.", "zone.", "sun.", "todo.", "button.", "input_"]
BLOCKED_DEVICE_CLASSES = ["timestamp", "enum", "update", "date", "identify"]
PRETTY_NAMES = {
    "temperature": "Temperatura", "humidity": "Wilgotność", "pressure": "Ciśnienie",
    "power": "Moc", "energy": "Energia", "voltage": "Napięcie", "current": "Natężenie",
    "battery": "Bateria", "signal_strength": "Sygnał", "pm25": "PM 2.5", "illuminance": "Jasność",
    "connectivity": "Połączenie"
}

# --- HELPER FUNCTIONS ---

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def wait_for_api():
    log(f"Checking API connection: {API_URL} ...")
    while True:
        try:
            r = requests.get(f"{API_URL}/", headers=HEADERS, timeout=5)
            if r.status_code in [200, 201, 401, 404, 405]:
                log(">>> API CONNECTION ESTABLISHED! <<<")
                return
        except Exception:
            pass
        time.sleep(5)

def install_and_register_card():
    """Copies card file and registers it in Lovelace"""
    if not SOURCE_CARD_FILE or not os.path.exists(SOURCE_CARD_FILE):
        return False, f"Source file not found. Checked: {POSSIBLE_PATHS}"

    # 1. Copy File
    DEST_FILE = os.path.join(HA_WWW_DIR, "employee-card.js")
    try:
        if not os.path.exists(HA_WWW_DIR):
            os.makedirs(HA_WWW_DIR)
        
        shutil.copy2(SOURCE_CARD_FILE, DEST_FILE)
        log(f">>> Card copied to {DEST_FILE}")
    except Exception as e:
        return False, f"File copy error: {str(e)}"

    # 2. Register in Lovelace
    api_url = f"{API_URL}/lovelace/resources"
    try:
        get_res = requests.get(api_url, headers=HEADERS)
        if get_res.status_code == 200:
            for res in get_res.json():
                if res['url'] == CARD_URL_RESOURCE:
                    return True, "Card updated (file overwritten)!"
        
        # Register new
        post_res = requests.post(api_url, headers=HEADERS, json={"type": "module", "url": CARD_URL_RESOURCE})
        if post_res.status_code in [200, 201]:
            return True, "Card registered successfully!"
        else:
            return False, f"API Error ({post_res.status_code}): {post_res.text}"
    except Exception as e:
        return False, f"API Connection Error: {str(e)}"

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS work_history
                     (work_date TEXT, employee_name TEXT, minutes_worked INTEGER, 
                     UNIQUE(work_date, employee_name))''')
        conn.commit()
        conn.close()
    except: pass

def log_minute_to_db(employee_name):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO work_history (work_date, employee_name, minutes_worked) VALUES (?, ?, 1)", (today, employee_name))
        except sqlite3.IntegrityError:
            c.execute("UPDATE work_history SET minutes_worked = minutes_worked + 1 WHERE work_date=? AND employee_name=?", (today, employee_name))
        conn.commit()
        conn.close()
    except: pass

def get_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

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

def load_status():
    if not os.path.exists(STATUS_FILE): return {"date": datetime.now().strftime("%Y-%m-%d"), "counters": {}}
    try:
        with open(STATUS_FILE, 'r') as f: return json.load(f)
    except: return {"date": datetime.now().strftime("%Y-%m-%d"), "counters": {}}

def save_status(status_data):
    try:
        with open(STATUS_FILE, 'w') as f: json.dump(status_data, f, indent=4)
    except: pass

def get_state_full(entity_id):
    if not entity_id: return None
    try:
        r = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def set_state(entity_id, state, friendly, icon, group, unit=None):
    attrs = {"friendly_name": friendly, "icon": icon, "group": group, "managed_by": "employee_manager"}
    if unit: attrs["unit_of_measurement"] = unit
    try: requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json={"state": str(state), "attributes": attrs})
    except: pass

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

def save_daily_report(work_counters, report_date):
    try:
        log(f">>> Generowanie raportu dobowego za {report_date}...")
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f: history = json.load(f)

        timestamp = f"{report_date} (Raport Dobowy)"
        snapshot = []
        groups_analysis = {}

        emps = get_data() 
        for emp in emps:
            name = emp['name']
            group = emp.get('group', 'Domyślna')
            
            work_time = 0.0
            if name in work_counters: work_time = round(work_counters[name], 1)
            
            snapshot.append({
                "name": name, 
                "group": group, 
                "work_time": work_time
            })

            if group not in groups_analysis:
                groups_analysis[group] = {"total_minutes": 0, "people_count": 0}
            
            groups_analysis[group]["total_minutes"] += work_time
            groups_analysis[group]["people_count"] += 1

        snapshot.sort(key=lambda x: (x['group'], x['name']))

        groups_summary = []
        for g_name, stats in groups_analysis.items():
            hours = round(stats["total_minutes"] / 60, 1)
            groups_summary.append({
                "group": g_name,
                "total_hours": hours,
                "avg_per_person": round(stats["total_minutes"] / stats["people_count"], 1) if stats["people_count"] > 0 else 0
            })
        
        groups_summary.sort(key=lambda x: x['group'])

        history.insert(0, {
            "id": int(time.time()), 
            "date": timestamp, 
            "entries": snapshot,
            "group_summary": groups_summary
        })
        
        if len(history) > 365: history = history[:365]

        with open(HISTORY_FILE, 'w') as f: json.dump(history, f, indent=4)
        log(">>> Raport dobowy zapisany.")
    except Exception as e:
        log(f"Błąd zapisu raportu: {e}")

# --- MAIN LOGIC LOOP (BACKGROUND THREAD) ---
def logic_loop():
    wait_for_api()
    # Try auto-install card on startup
    install_and_register_card()
    
    log(f"=== START SYSTEMU LOGIKI ===")
    init_db()
    
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    
    work_counters = memory.get("counters", {})
    last_loop_date = today_str

    while True:
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # Raport o północy
            if current_date != last_loop_date:
                save_daily_report(work_counters, last_loop_date)
                work_counters = {}
                memory["date"] = current_date
                memory["counters"] = {}
                save_status(memory)
                last_loop_date = current_date

            emps = get_data()
            group_stats = {} 

            for emp in emps:
                name = emp['name'].strip()
                safe = name.lower().replace(" ", "_")
                group = emp.get('group', 'Domyślna')

                if group not in group_stats:
                    group_stats[group] = {"active_count": 0, "total_power": 0.0, "temps": [], "humidities": []}

                if name not in work_counters: work_counters[name] = 0.0
                is_working = False
                
                for eid in emp.get('sensors', []):
                    data = get_state_full(eid)
                    if not data: continue
                    state_val = data['state']
                    if state_val in ['unavailable', 'unknown', 'None']: continue
                    
                    attrs = data.get('attributes', {})
                    unit = attrs.get('unit_of_measurement')
                    
                    # Zbieranie statystyk grupowych
                    try:
                        f_val = float(state_val)
                        if unit == '°C': group_stats[group]["temps"].append(f_val)
                        elif unit == '%': group_stats[group]["humidities"].append(f_val)
                        elif unit == 'W' or unit == 'kW':
                             p_val = f_val * 1000 if unit == 'kW' else f_val
                             group_stats[group]["total_power"] += p_val
                    except: pass

                    # Logika "Pracuje" - FIXED INDENTATION
                    if unit == 'W' or unit == 'kW':
                        try:
                            val = float(state_val)
                            if unit == 'kW': val *= 1000
                            power_threshold = float(emp.get('threshold', 20.0))
                            if val > power_threshold: is_working = True
                        except: pass
                    
                    if eid.startswith("binary_sensor.") and state_val == 'on': 
                        is_working = True
                    
                    # Tworzenie sensorów pomocniczych (np. temp, bateria)
                    suffix_info = None
                    if unit in UNIT_MAP: suffix_info = UNIT_MAP[unit]
                    if suffix_info:
                        set_state(f"sensor.{safe}_{suffix_info['suffix']}", state_val, f"{name} {suffix_info['suffix']}", suffix_info['icon'], group, unit)

                status = "Pracuje" if is_working else "Nieobecny"
                if is_working: 
                    work_counters[name] += (10/60)
                    group_stats[group]["active_count"] += 1
                    log_minute_to_db(name)
                
                set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:laptop" if is_working else "mdi:account-off", group)
                set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", group, "min")

            # Tworzenie sensorów grupowych
            for grp_name, stats in group_stats.items():
                if grp_name == "Domyślna": continue
                safe_grp = grp_name.lower().replace(" ", "_")
                
                set_state(f"binary_sensor.grupa_{safe_grp}_zajetosc", "on" if stats["active_count"] > 0 else "off", f"Pomieszczenie {grp_name}", "mdi:account-group", grp_name)
                
                if stats["total_power"] > 0:
                    set_state(f"sensor.grupa_{safe_grp}_moc", round(stats["total_power"], 1), f"{grp_name} - Moc", "mdi:lightning-bolt", grp_name, "W")
                
                if len(stats["temps"]) > 0:
                    avg_temp = sum(stats["temps"]) / len(stats["temps"])
                    set_state(f"sensor.grupa_{safe_grp}_temperatura", round(avg_temp, 1), f"{grp_name} - Temp", "mdi:thermometer", grp_name, "°C")

            memory["counters"] = work_counters
            save_status(memory)
            
        except Exception as e:
            log(f"Krytyczny błąd w pętli: {e}")

        time.sleep(10)

# --- START BACKGROUND LOGIC ---
threading.Thread(target=logic_loop, daemon=True).start()


# --- WEB SERVER ROUTES (FLASK) ---

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
        for suffix in MANAGED_SUFFIXES:
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
        res.append({"name": emp['name'], "group": emp.get('group', 'Domyślna'), "status": status, "work_time": time, "measurements": meas})
    return jsonify(res)

@app.route('/download_report')
def download_report():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute("SELECT work_date, employee_name, minutes_worked FROM work_history ORDER BY work_date DESC")
        rows = c.fetchall()
        conn.close()
        
        si = io.StringIO()
        cw = csv.writer(si, delimiter=';')
        cw.writerow(["Data", "Pracownik", "Minuty", "Godziny"])
        for r in rows:
            cw.writerow([r[0], r[1], r[2], round(r[2]/60, 2)])
            
        return Response(si.getvalue(), mimetype="text/csv", headers={"Content-disposition": "attachment; filename=Raport.csv"})
    except: return "Błąd", 500

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

@app.route('/local/employee-card.js')
def serve_card_file():
    if SOURCE_CARD_FILE and os.path.exists(SOURCE_CARD_FILE):
        return send_file(SOURCE_CARD_FILE, mimetype='application/javascript')
    return "Not found", 404

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)