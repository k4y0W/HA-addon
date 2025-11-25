import os
import time
import requests
import json
import sys

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
API_URL = "http://supervisor/core/api"
HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    "Content-Type": "application/json",
}
DATA_FILE = "/data/employees.json"

def log(message): print(f"[Logic] {message}", flush=True)

def get_data():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def get_state_full(entity_id):
    if not entity_id: return None
    try:
        r = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
        if r.status_code == 200: return r.json()
    except: pass
    return None

def set_state(entity_id, state, friendly, icon, unit=None):
    pl = {"state": state, "attributes": {"friendly_name": friendly, "icon": icon}}
    if unit: pl["attributes"]["unit_of_measurement"] = unit
    requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json=pl)

def main():
    log("Startuję logikę (Auto-Sensors)...")
    work_counters = {}

    while True:
        emps = get_data()
        for emp in emps:
            name = emp['name']
            safe = name.lower().replace(" ", "_")
            
            # 1. STATUS / CZAS (Bazowane na mocy)
            # Szukamy wśród przypisanych czujników takiego, który mierzy W (Waty)
            power_val = 0
            assigned_ids = emp.get('sensors', [])
            
            for eid in assigned_ids:
                data = get_state_full(eid)
                if data:
                    unit = data['attributes'].get('unit_of_measurement', '')
                    if unit == 'W': # Znalazłem gniazdko!
                        try: power_val = float(data['state'])
                        except: pass
                        break
            
            if name not in work_counters: work_counters[name] = 0.0
            
            status = "Obecny (Idle)"
            if power_val > 20.0: # Próg
                status = "Pracuje"
                work_counters[name] += (10/60)
            elif power_val == 0:
                status = "Nieobecny"

            set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:account")
            set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", "min")

            # 2. KOPIOWANIE SENSORÓW (Dla karty Lovelace)
            # Tworzymy wirtualne sensory (np. sensor.jan_temperatura) na podstawie wybranych
            for eid in assigned_ids:
                data = get_state_full(eid)
                if data:
                    val = data['state']
                    unit = data['attributes'].get('unit_of_measurement', '')
                    original_name = data['attributes'].get('friendly_name', 'Czujnik')
                    
                    # Próbujemy zgadnąć suffix (temperatura/wilgotnosc) na podstawie jednostki
                    suffix = "pomiar"
                    icon = "mdi:eye"
                    if unit == "°C": suffix = "temperatura"; icon="mdi:thermometer"
                    elif unit == "%": suffix = "wilgotnosc"; icon="mdi:water-percent"
                    elif unit == "hPa": suffix = "cisnienie"; icon="mdi:gauge"
                    
                    # Tworzymy sensor.jan_temperatura
                    set_state(f"sensor.{safe}_{suffix}", val, f"{name} - {original_name}", icon, unit)

        time.sleep(10)

if __name__ == "__main__":
    main()