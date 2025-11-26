import os
import time
import requests
import json
from datetime import datetime

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
API_URL = "http://supervisor/core/api"
HEADERS = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"}
DATA_FILE = "/data/employees.json"
STATUS_FILE = "/data/status.json"

def get_data():
    try: with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def get_state_full(entity_id):
    try:
        r = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
        return r.json() if r.status_code == 200 else None
    except: return None

# Funkcja wysyłająca stan wraz z grupą
def set_state(entity_id, state, friendly, icon, group, unit=None):
    attrs = {"friendly_name": friendly, "icon": icon, "group": group} # <-- TU JEST GRUPA!
    if unit: attrs["unit_of_measurement"] = unit
    requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json={"state": state, "attributes": attrs})

def main():
    print("Startuję logikę z grupami...", flush=True)
    # ... (Tutaj wstaw logikę wczytywania liczników z pliku status.json jak wcześniej) ...
    work_counters = {} 

    while True:
        emps = get_data()
        for emp in emps:
            name = emp['name']
            group = emp.get('group', 'Domyślna') # Pobieramy grupę
            safe = name.lower().replace(" ", "_")
            
            if name not in work_counters: work_counters[name] = 0.0
            
            # --- LOGIKA OR (LUB) ---
            is_working = False
            
            # 1. Sprawdź MOC
            for eid in emp.get('sensors', []):
                data = get_state_full(eid)
                if data and data['attributes'].get('unit_of_measurement') == 'W':
                    try:
                        if float(data['state']) > 20.0: is_working = True
                    except: pass
            
            # 2. Sprawdź RUCH (Binary Sensor) - jeśli moc nie wykryła
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

        time.sleep(10)

if __name__ == "__main__":
    main()