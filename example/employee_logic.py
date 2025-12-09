import os
import time
import requests
import json
import sys
import sqlite3
from datetime import datetime

HARDCODED_TOKEN = ""
DATA_FILE = "/data/employees.json"
STATUS_FILE = "/data/status.json"
OPTIONS_FILE = "/data/options.json"
DB_FILE = "/data/employee_history.db"

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS work_history
                     (work_date TEXT, employee_name TEXT, minutes_worked INTEGER, 
                     UNIQUE(work_date, employee_name))''')
        conn.commit()
        conn.close()
        log(f"Baza danych zainicjowana: {DB_FILE}")
    except Exception as e:
        log(f"Błąd inicjalizacji bazy: {e}")

def log_minute_to_db(employee_name):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO work_history (work_date, employee_name, minutes_worked) VALUES (?, ?, 1)", 
                      (today, employee_name))
        except sqlite3.IntegrityError:
            c.execute("UPDATE work_history SET minutes_worked = minutes_worked + 1 WHERE work_date=? AND employee_name=?", 
                      (today, employee_name))
        conn.commit()
        conn.close()
    except Exception as e:
        log(f"Błąd zapisu do bazy dla {employee_name}: {e}")

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
USER_TOKEN_FROM_FILE = ""

try:
    if os.path.exists(OPTIONS_FILE):
        with open(OPTIONS_FILE, 'r') as f:
            opts = json.load(f)
            USER_TOKEN_FROM_FILE = opts.get("ha_token", "")
except: pass

if len(HARDCODED_TOKEN) > 50:
    log(">>> UŻYWAM TOKENA HARDCODED (Tryb Administratora) <<<")
    TOKEN = HARDCODED_TOKEN
    API_URL = "http://homeassistant:8123/api"
elif len(USER_TOKEN_FROM_FILE) > 50:
    log(">>> UŻYWAM TOKENA Z PLIKU (Tryb Administratora) <<<")
    TOKEN = USER_TOKEN_FROM_FILE
    API_URL = "http://homeassistant:8123/api"
else:
    log(">>> BRAK TOKENA USERA - UŻYWAM SUPERVISORA (Brak usuwania!) <<<")
    TOKEN = SUPERVISOR_TOKEN
    API_URL = "http://supervisor/core/api"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}

UNIT_MAP = {
    "W": {"suffix": "moc", "icon": "mdi:lightning-bolt"},
    "kW": {"suffix": "moc", "icon": "mdi:lightning-bolt"},
    "V": {"suffix": "napiecie", "icon": "mdi:sine-wave"},
    "A": {"suffix": "natezenie", "icon": "mdi:current-ac"},
    "°C": {"suffix": "temperatura", "icon": "mdi:thermometer"},
    "%": {"suffix": "wilgotnosc", "icon": "mdi:water-percent"},
    "hPa": {"suffix": "cisnienie", "icon": "mdi:gauge"},
    "µg/m³": {"suffix": "pm25", "icon": "mdi:blur"},
}

MANAGED_SUFFIXES = [
    "_status", "_czas_pracy","Iphone"
]

BLOCKED_KEYWORDS = [
    "App Version", "Audio Output", "BSSID", "SSID", "Connection Type", 
    "Geocoded Location", "Last Update Trigger", "Location permission", 
    "SIM 1", "SIM 2", "Storage", "Battery State", "Activity", "Focus",
    "Distance Traveled", "Floors Ascended", "Steps", "Average Active Pace"
]

def get_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def load_status():
    if not os.path.exists(STATUS_FILE): 
        return {"date": datetime.now().strftime("%Y-%m-%d"), "counters": {}}
    try:
        with open(STATUS_FILE, 'r') as f: return json.load(f)
    except:
        return {"date": datetime.now().strftime("%Y-%m-%d"), "counters": {}}

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
    attrs = {"friendly_name": friendly, "icon": icon, "group": group}
    if unit: attrs["unit_of_measurement"] = unit
    try:
        requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json={"state": str(state), "attributes": attrs})
    except Exception as e:
        log(f"Błąd ustawiania {entity_id}: {e}")

def delete_entity_force(entity_id):
    try:
        log(f"-> PRÓBA USUNIĘCIA: {entity_id}")
        r = requests.delete(f"{API_URL}/states/{entity_id}", headers=HEADERS)
        if r.status_code in [200, 201, 204]:
            log(f"   SUKCES! Usunięto {entity_id}")
        else:
            log(f"   BŁĄD API! Kod: {r.status_code}, Treść: {r.text}")
    except Exception as e:
        log(f"   WYJĄTEK: {e}")

def main():
    log(f"=== START SYSTEMU (API: {API_URL}) ===")
    init_db()
    
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    work_counters = memory.get("counters", {})

    loop_counter = 0

    while True:
        try:
            emps = get_data()
            allowed_ids = set()

            loop_counter += 1
            should_save_db = False
            
            if loop_counter >= 6:
                should_save_db = True
                loop_counter = 0

            for emp in emps:
                name = emp['name'].strip()
                safe = name.lower().replace(" ", "_")
                group = emp.get('group', 'Domyślna')

                allowed_ids.add(f"sensor.{safe}_status")
                allowed_ids.add(f"sensor.{safe}_czas_pracy")

                for eid in emp.get('sensors', []):
                    data = get_state_full(eid)
                    if not data: continue
                    attrs = data.get('attributes', {})
                    unit = attrs.get('unit_of_measurement')
                    dev_class = attrs.get('device_class')

                    suffix_info = None
                    if unit in UNIT_MAP:
                        suffix_info = UNIT_MAP[unit]
                        if unit == '%' and dev_class == 'battery':
                            suffix_info = {"suffix": "bateria", "icon": "mdi:battery"}
                    elif dev_class == 'battery':
                        suffix_info = {"suffix": "bateria", "icon": "mdi:battery"}
                    
                    if suffix_info:
                        allowed_ids.add(f"sensor.{safe}_{suffix_info['suffix']}")

            try:
                r = requests.get(f"{API_URL}/states", headers=HEADERS)
                if r.status_code == 200:
                    all_states = r.json()
                    for entity in all_states:
                        eid = entity['entity_id']
                        if not eid.startswith("sensor."): continue

                        is_managed = False
                        for suffix in MANAGED_SUFFIXES:
                            if eid.endswith(suffix):
                                is_managed = True
                                break
                        
                        if is_managed:
                            if eid not in allowed_ids:
                                delete_entity_force(eid)
                                
            except Exception as e:
                log(f"Błąd skanowania: {e}")

            current_date_str = datetime.now().strftime("%Y-%m-%d")
            if current_date_str != memory["date"]:
                memory["date"] = current_date_str
                work_counters = {}
                memory["counters"] = {}
                save_status(memory)

            for emp in emps:
                name = emp['name'].strip()
                safe = name.lower().replace(" ", "_")
                group = emp.get('group', 'Domyślna')

                if name not in work_counters: work_counters[name] = 0.0
                is_working = False
                
                for eid in emp.get('sensors', []):
                    data = get_state_full(eid)
                    if not data: continue
                    state_val = data['state']
                    if state_val in ['unavailable', 'unknown', 'None']: continue
                    attrs = data.get('attributes', {})
                    unit = attrs.get('unit_of_measurement')
                    dev_class = attrs.get('device_class')

                    if unit == 'W' or unit == 'kW':
                        try:
                            val = float(state_val)
                            if unit == 'kW': val *= 1000
                            if val > 20.0: is_working = True
                        except: pass
                    
                    suffix_info = None
                    if unit in UNIT_MAP:
                        suffix_info = UNIT_MAP[unit]
                        if unit == '%' and dev_class == 'battery':
                            suffix_info = {"suffix": "bateria", "icon": "mdi:battery"}
                    elif dev_class == 'battery':
                        suffix_info = {"suffix": "bateria", "icon": "mdi:battery"}

                    if suffix_info:
                        v_id = f"sensor.{safe}_{suffix_info['suffix']}"
                        set_state(v_id, state_val, f"{name} {suffix_info['suffix']}", suffix_info['icon'], group, unit)

                if not is_working:
                    for eid in emp.get('sensors', []):
                        if eid.startswith("binary_sensor."):
                            data = get_state_full(eid)
                            if data and data['state'] == 'on':
                                is_working = True
                
                status = "Pracuje" if is_working else "Nieobecny"
                if is_working: 
                    work_counters[name] += (10/60)
                    
                if is_working and should_save_db:
                    log_minute_to_db(name)
                
                set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:laptop" if is_working else "mdi:account-off", group)
                set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", group, "min")

            memory["counters"] = work_counters
            save_status(memory)
            
        except Exception as e:
            log(f"Krytyczny błąd: {e}")

        time.sleep(10)

if __name__ == "__main__":
    main()