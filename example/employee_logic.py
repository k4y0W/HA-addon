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

# --- TO JEST KLUCZOWE DLA IKONEK NA KARCIE ---
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
# ---------------------------------------------

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
    except: pass

def main():
    print("Startuję naprawioną logikę (obsługa ikonek)...", flush=True)
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    work_counters = memory.get("counters", {})

    while True:
        try:
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
                # Jeśli brak grupy, wpisujemy Domyślna - to ważne dla filtrów karty
                group = emp.get('group', 'Domyślna') 
                safe = name.lower().replace(" ", "_")
                
                if name not in work_counters: work_counters[name] = 0.0
                
                is_working = False
                
                # --- PĘTLA PO CZUJNIKACH ---
                for eid in emp.get('sensors', []):
                    data = get_state_full(eid)
                    if not data: continue
                    
                    state_val = data['state']
                    if state_val in ['unavailable', 'unknown', 'None']: continue
                    
                    attrs = data.get('attributes', {})
                    unit = attrs.get('unit_of_measurement')
                    dev_class = attrs.get('device_class')

                    # 1. LOGIKA PRACY (Waty)
                    # Dodano obsługę kW (razy 1000), bo to częsty błąd
                    if unit == 'W' or unit == 'kW':
                        try:
                            val = float(state_val)
                            if unit == 'kW': val *= 1000
                            if val > 20.0: is_working = True
                        except: pass
                    
                    # 2. TWORZENIE IKONEK (tego brakowało w Twoim kodzie!)
                    suffix_info = None
                    if unit in UNIT_MAP:
                        suffix_info = UNIT_MAP[unit]
                        # Rozróżnienie % (Bateria vs Wilgotność)
                        if unit == '%' and dev_class == 'battery':
                            suffix_info = {"suffix": "bateria", "icon": "mdi:battery"}
                    elif dev_class == 'battery':
                        suffix_info = {"suffix": "bateria", "icon": "mdi:battery"}

                    # Jeśli znaleziono pasujący typ, wyślij do HA jako wirtualny sensor
                    if suffix_info:
                        v_id = f"sensor.{safe}_{suffix_info['suffix']}"
                        set_state(
                            v_id, 
                            state_val, 
                            f"{name} {suffix_info['suffix']}", 
                            suffix_info['icon'], 
                            group, 
                            unit
                        )

                # 3. LOGIKA RUCHU (Binary Sensor)
                if not is_working:
                    for eid in emp.get('sensors', []):
                        if eid.startswith("binary_sensor."):
                            data = get_state_full(eid)
                            if data and data['state'] == 'on':
                                is_working = True
                
                status = "Pracuje" if is_working else "Nieobecny"
                if is_working: work_counters[name] += (10/60)
                
                # Aktualizacja głownych sensorów
                # Używamy ikonki laptopa, gdy pracuje
                main_icon = "mdi:laptop" if is_working else "mdi:account-off"
                
                set_state(f"sensor.{safe}_status", status, f"{name} - Status", main_icon, group)
                set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", group, "min")

            # Zapisz stan
            memory["counters"] = work_counters
            save_status(memory)
            
        except Exception as e:
            print(f"Błąd pętli: {e}", flush=True)

        time.sleep(10)

if __name__ == "__main__":
    main()