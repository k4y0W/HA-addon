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

# --- MAPOWANIE DLA IKONEK ---
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

# Lista końcówek, którymi zarządza ten dodatek
MANAGED_SUFFIXES = [
    "_status", "_czas_pracy", 
    "_moc", "_napiecie", "_natezenie", 
    "_temperatura", "_wilgotnosc", "_cisnienie", 
    "_bateria", "_pm25"
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
    except: pass

def delete_state(entity_id):
    """Bezpowrotnie usuwa encję z HA"""
    try:
        print(f"!!! USUWANIE DUCHA: {entity_id} !!!", flush=True)
        requests.delete(f"{API_URL}/states/{entity_id}", headers=HEADERS)
    except Exception as e:
        print(f"Błąd usuwania {entity_id}: {e}", flush=True)

# --- NOWA LOGIKA: GENEROWANIE OCZEKIWANYCH ID ---
def get_expected_ids(employees):
    """Zwraca zbiór wszystkich ID, które POWINNY istnieć w systemie."""
    expected = set()
    for emp in employees:
        safe = emp['name'].lower().replace(" ", "_")
        
        # 1. Główne sensory
        expected.add(f"sensor.{safe}_status")
        expected.add(f"sensor.{safe}_czas_pracy")
        
        # 2. Sensory z czujników (dynamiczne)
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
                expected.add(f"sensor.{safe}_{suffix_info['suffix']}")
    
    return expected

def purge_ghosts(expected_ids):
    """Usuwa wszystko z HA co wygląda jak nasze, a nie jest na liście expected_ids"""
    try:
        r = requests.get(f"{API_URL}/states", headers=HEADERS)
        if r.status_code != 200: return
        all_states = r.json()

        for entity in all_states:
            eid = entity['entity_id']
            if not eid.startswith("sensor."): continue
            
            # Sprawdź czy to "nasz" typ sensora (ma jedną z naszych końcówek)
            is_ours = False
            for suffix in MANAGED_SUFFIXES:
                if eid.endswith(suffix):
                    is_ours = True
                    break
            
            if is_ours:
                # KLUCZOWY MOMENT: Czy ten sensor jest na liście oczekiwanych?
                if eid not in expected_ids:
                    # Jeśli to sensor systemowy HA (rzadkie, ale możliwe), pomiń
                    if "backup" in eid or "hacs" in eid: continue
                    
                    # Jeśli nie ma go na liście -> KASUJ
                    delete_state(eid)
                    
    except Exception as e:
        print(f"Błąd purge: {e}", flush=True)

def main():
    print("Startuję Logikę: Strict Whitelist Mode...", flush=True)
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    work_counters = memory.get("counters", {})

    while True:
        try:
            emps = get_data()
            
            # --- KROK 1: Wylicz co powinno być ---
            expected_ids = get_expected_ids(emps)
            
            # --- KROK 2: Usuń wszystko inne ---
            purge_ghosts(expected_ids)
            
            # --- KROK 3: Aktualizuj to co zostało ---
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
                
                if name not in work_counters: work_counters[name] = 0.0
                is_working = False
                
                # Logika sensorów (detekcja pracy)
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
                    
                    # Generowanie sensorów (te ID trafiły już do expected_ids)
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
            print(f"Błąd pętli: {e}", flush=True)

        time.sleep(10)

if __name__ == "__main__":
    main()