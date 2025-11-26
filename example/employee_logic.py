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

# --- PRZYWRÓCONE FUNKCJE STANU ---
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
# ---------------------------------

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
    requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json={"state": state, "attributes": attrs})

def main():
    print("Startuję logikę z grupami...", flush=True)
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    work_counters = memory.get("counters", {})

    while True:
        emps = get_data()
        current_date_str = datetime.now().strftime("%Y-%m-%d")
        
        # Reset o północy
        if current_date_str != memory["date"]:
            memory["date"] = current_date_str
            work_counters = {}
            memory["counters"] = {}
            save_status(memory)

        for emp in emps:
            name = emp['name']
            group = emp.get('group', 'Domyślna')
            safe = name.lower().replace(" ", "_")
            
            if name not in work_counters: work_counters[name] = 0.0
            
            is_working = False
            
            # 1. Sprawdź MOC
            for eid in emp.get('sensors', []):
                data = get_state_full(eid)
                if data and data['attributes'].get('unit_of_measurement') == 'W':
                    try:
                        if float(data['state']) > 20.0: is_working = True
                    except: pass
            
            # 2. Sprawdź RUCH (Binary Sensor)
            if not is_working:
                for eid in emp.get('sensors', []):
                    if eid.startswith("binary_sensor."):
                        data = get_state_full(eid)
                        if data and data['state'] == 'on':
                            is_working = True
            
            status = "Pracuje" if is_working else "Nieobecny"
            if is_working: work_counters[name] += (10/60)
            
            # Aktualizacja sensorów z atrybutem GRUPY
            set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:account", group)
            set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", group, "min")

        # Zapisz stan
        memory["counters"] = work_counters
        save_status(memory)
        
        time.sleep(10)

if __name__ == "__main__":
    main()