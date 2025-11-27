import os
import time
import requests
import json
import sys
from datetime import datetime

# ==========================================
# TUTAJ WKLEJ SWÓJ DŁUGI TOKEN:
HARDCODED_TOKEN = "TUTAJ_WKLEJ_TOKEN"
# ==========================================

DATA_FILE = "/data/employees.json"
STATUS_FILE = "/data/status.json"

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
if len(HARDCODED_TOKEN) > 50:
    print(">>> UŻYWAM TOKENA HARDCODED (Tryb Administratora) <<<", flush=True)
    TOKEN = HARDCODED_TOKEN
    API_URL = "http://homeassistant:8123/api"
else:
    print(">>> BRAK TOKENA USERA - UŻYWAM SUPERVISORA (Brak usuwania!) <<<", flush=True)
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
    "_status", "_czas_pracy", "_moc", "_napiecie", "_natezenie", 
    "_temperatura", "_wilgotnosc", "_cisnienie", "_bateria", "_pm25", "_jasnosc"
]

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

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
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    work_counters = memory.get("counters", {})

    while True:
        try:
            emps = get_data()
            allowed_ids = set()

            for emp in emps:
                name_clean = emp['name'].strip()
                safe = name_clean.lower().replace(" ", "_")
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
                if is_working: work_counters[name] += (10/60)
                
                set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:laptop" if is_working else "mdi:account-off", group)
                set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", group, "min")

            memory["counters"] = work_counters
            save_status(memory)
            
        except Exception as e:
            log(f"Krytyczny błąd: {e}")

        time.sleep(10)

if __name__ == "__main__":
    main()