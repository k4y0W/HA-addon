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

def log(message):
    print(f"[Logic] {message}", flush=True)

# --- POPRAWIONA FUNKCJA (BŁĄD SKŁADNI NAPRAWIONY) ---
def get_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

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
    log("Startuję logikę (z obsługą PM2.5)...")
    work_counters = {}

    while True:
        emps = get_data()
        for emp in emps:
            name = emp['name']
            safe = name.lower().replace(" ", "_")
            
            # 1. STATUS PRACY (Szukamy Watów 'W')
            power_val = 0
            assigned_ids = emp.get('sensors', [])
            
            for eid in assigned_ids:
                data = get_state_full(eid)
                if data:
                    unit = data['attributes'].get('unit_of_measurement', '')
                    if unit == 'W': 
                        try: power_val = float(data['state'])
                        except: pass
                        break 
            
            if name not in work_counters: work_counters[name] = 0.0
            
            status = "Obecny (Idle)"
            if power_val > 20.0:
                status = "Pracuje"
                work_counters[name] += (10/60)
            elif power_val == 0 and len(assigned_ids) > 0:
                status = "Nieobecny"

            set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:account")
            set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", "min")

            # 2. KOPIOWANIE SENSORÓW
            for eid in assigned_ids:
                data = get_state_full(eid)
                if data:
                    val = data['state']
                    unit = data['attributes'].get('unit_of_measurement', '')
                    friendly = data['attributes'].get('friendly_name', eid)
                    
                    suffix = "sensor"
                    icon = "mdi:eye"
                    
                    # ROZPOZNAWANIE JEDNOSTEK
                    if unit == "°C": suffix = "temperatura"; icon="mdi:thermometer"
                    elif unit == "%": suffix = "wilgotnosc"; icon="mdi:water-percent"
                    elif unit == "hPa": suffix = "cisnienie"; icon="mdi:gauge"
                    elif unit == "W": suffix = "moc"; icon="mdi:lightning-bolt"
                    elif unit == "V": suffix = "napiecie"; icon="mdi:sine-wave"
                    elif unit == "A": suffix = "natezenie"; icon="mdi:current-ac"
                    elif unit == "µg/m³": suffix = "pm25"; icon="mdi:blur"
                    elif unit == "µg/m³": { suffix: 'pm25_density', icon: 'mdi:blur', unit: 'μg/m³' }, { suffix: 'pm25', icon: 'mdi:blur', unit: 'μg/m³' }
                    
                    set_state(f"sensor.{safe}_{suffix}", val, f"{name} - {friendly}", icon, unit)

        time.sleep(10)

if __name__ == "__main__":
    main()