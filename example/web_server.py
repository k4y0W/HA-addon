import os
import time
import requests
import json
import sys
from datetime import datetime

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
API_URL = "http://supervisor/core/api"
HEADERS = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"}
DATA_FILE = "/data/employees.json"
STATUS_FILE = "/data/status.json"

def get_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

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
        return r.json() if r.status_code == 200 else None
    except: return None

def set_state(entity_id, state, friendly, icon, group, unit=None):
    pl = {"state": state, "attributes": {"friendly_name": friendly, "icon": icon, "group": group}}
    if unit: pl["attributes"]["unit_of_measurement"] = unit
    requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json=pl)

def delete_entity(entity_id):
    try: requests.delete(f"{API_URL}/states/{entity_id}", headers=HEADERS)
    except: pass

def cleanup_ghosts(current_employees):
    active_safe_names = [emp['name'].lower().replace(" ", "_") for emp in current_employees]
    MANAGED_SUFFIXES = ["status", "czas_pracy", "temperatura", "wilgotnosc", "cisnienie", "moc", "napiecie", "natezenie", "pm25", "bateria"]
    try:
        r = requests.get(f"{API_URL}/states", headers=HEADERS)
        if r.status_code != 200: return
        for entity in r.json():
            eid = entity['entity_id']
            if not eid.startswith("sensor."): continue
            is_managed = False
            name_part = ""
            for suffix in MANAGED_SUFFIXES:
                if eid.endswith(f"_{suffix}"):
                    parts = eid.split(f"_{suffix}")
                    if len(parts) > 0:
                        name_part = parts[0].replace("sensor.", "")
                        is_managed = True
                        break
            if is_managed and name_part not in active_safe_names:
                delete_entity(eid)
    except: pass

def main():
    print("Startuję logikę z grupami...", flush=True)
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    work_counters = memory.get("counters", {})

    while True:
        emps = get_data()
        cleanup_ghosts(emps)
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        if current_date_str != memory["date"]:
            memory["date"] = current_date_str
            work_counters = {}
            memory["counters"] = {}
            save_status(memory)

        for emp in emps:
            name = emp['name']
            group = emp.get('group', 'Domyślna')
            safe = name.lower().replace(" ", "_")
            assigned_ids = emp.get('sensors', [])
            
            if name not in work_counters: work_counters[name] = 0.0
            
            is_present = False
            power_threshold_reached = False
            
            for eid in assigned_ids:
                data = get_state_full(eid)
                if data:
                    unit = data['attributes'].get('unit_of_measurement', '')
                    state = data['state']
                    
                    if eid.startswith('binary_sensor.') and state == 'on': is_present = True
                    if unit == 'W': 
                        try:
                            if float(state or 0) > 20.0: power_threshold_reached = True
                        except: pass
            
            status = "Nieobecny"
            is_working = False

            if power_threshold_reached:
                if is_present: status = "Pracuje"
                else: status = "Pracuje (Brak ruchu)"
                is_working = True
            elif is_present and not power_threshold_reached:
                status = "Obecny (Idle)"
            
            if is_working: work_counters[name] += (10/60)

            set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:account", group)
            set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", group, "min")

            for eid in assigned_ids:
                data = get_state_full(eid)
                if data:
                    val = data['state']
                    unit = data['attributes'].get('unit_of_measurement', '')
                    friendly = data['attributes'].get('friendly_name', eid)
                    
                    suffix = "sensor"
                    icon = "mdi:eye"
                    
                    if unit == "°C": suffix = "temperatura"; icon="mdi:thermometer"
                    elif unit == "%": suffix = "wilgotnosc"; icon="mdi:water-percent"
                    elif unit == "hPa": suffix = "cisnienie"; icon="mdi:gauge"
                    elif unit == "W": suffix = "moc"; icon="mdi:lightning-bolt"
                    elif unit == "V": suffix = "napiecie"; icon="mdi:sine-wave"
                    elif unit == "A": suffix = "natezenie"; icon="mdi:current-ac"
                    elif unit == "µg/m³": suffix = "pm25"; icon="mdi:blur"
                    
                    set_state(f"sensor.{safe}_{suffix}", val, f"{name} - {friendly}", icon, unit)

        memory["counters"] = work_counters
        save_status(memory)
        time.sleep(10)

if __name__ == "__main__":
    main()