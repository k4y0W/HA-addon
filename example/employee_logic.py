import os
import time
import requests
import json
import sys
import sqlite3
import shutil
from datetime import datetime

# --- KONFIGURACJA PLIKÓW ---
DATA_FILE = "/data/employees.json"
STATUS_FILE = "/data/status.json"
OPTIONS_FILE = "/data/options.json"
DB_FILE = "/data/employee_history.db"
HISTORY_FILE = "/data/history.json"

# Konfiguracja instalacji karty
SOURCE_JS_FILE = "/employee-card.js"
HA_WWW_DIR = "/config/www"
DEST_JS_FILE = os.path.join(HA_WWW_DIR, "employee-card.js")
CARD_URL_RESOURCE = "/local/employee-card.js"

# --- KONFIGURACJA API I TOKENA ---
TOKEN = ""
API_URL = ""

# 1. Próba pobrania tokena z pliku opcji
try:
    if os.path.exists(OPTIONS_FILE):
        with open(OPTIONS_FILE, 'r') as f:
            opts = json.load(f)
            TOKEN = opts.get("ha_token", "").strip()
except:
    pass

# 2. Wybór trybu działania
if len(TOKEN) > 50:
    API_URL = "http://172.30.32.1:8123/api"
    print(f">>> [LOGIC] TRYB RĘCZNY: Używam tokena użytkownika. Adres: {API_URL}", flush=True)
else:
    TOKEN = os.environ.get("SUPERVISOR_TOKEN", "")
    API_URL = "http://supervisor/core/api"
    print(">>> [LOGIC] TRYB SUPERVISOR: Używam tokena systemowego.", flush=True)

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

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

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)

def wait_for_api():
    """Wstrzymuje start do momentu nawiązania połączenia z HA"""
    log(f"Sprawdzanie połączenia z API: {API_URL} ...")
    while True:
        try:
            r = requests.get(f"{API_URL}/", headers=HEADERS, timeout=5)
            if r.status_code in [200, 201, 401, 404, 405]:
                if r.status_code == 401:
                    log("!!! OSTRZEŻENIE: API zwróciło 401 (Unauthorized). Sprawdź czy token jest poprawny!")
                log(">>> POŁĄCZENIE NAWIĄZANE! Startuję logikę sensorów. <<<")
                return
        except Exception:
            pass
        
        log("Oczekiwanie na Home Assistant... (Ponowna próba za 10s)")
        time.sleep(10)

def auto_install_card():
    """Automatycznie instaluje lub aktualizuje kartę w HA"""
    log(">>> [AUTO-INSTALL] Rozpoczynam automatyczną instalację karty...")
    
    # 1. Kopiowanie pliku
    try:
        if not os.path.exists(HA_WWW_DIR):
            os.makedirs(HA_WWW_DIR)
        shutil.copy(SOURCE_JS_FILE, DEST_JS_FILE)
        log(f"   [OK] Plik skopiowany do {DEST_JS_FILE}")
    except Exception as e:
        log(f"   [BŁĄD] Nie udało się skopiować pliku: {e}")
        return

    # 2. Rejestracja w Zasobach HA
    try:
        url = f"{API_URL}/lovelace/resources"
        # Sprawdzenie czy już jest
        get_resp = requests.get(url, headers=HEADERS)
        
        if get_resp.status_code == 200:
            resources = get_resp.json()
            for res in resources:
                if res['url'] == CARD_URL_RESOURCE:
                    log("   [INFO] Karta jest już zarejestrowana w zasobach.")
                    return # Jest ok, nie trzeba nic robić

        # Jeśli nie ma, to dodajemy
        payload = {"url": CARD_URL_RESOURCE, "type": "module"}
        post_resp = requests.post(url, headers=HEADERS, json=payload)
        
        if post_resp.status_code in [200, 201]: 
            log("   [SUKCES] Karta została dodana do zasobów Lovelace!")
        else: 
            log(f"   [BŁĄD API] Kod: {post_resp.status_code}, Treść: {post_resp.text}")
            
    except Exception as e: 
        log(f"   [BŁĄD KRYTYCZNY] Podczas rejestracji karty: {e}")


def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS work_history
                     (work_date TEXT, employee_name TEXT, minutes_worked INTEGER, 
                     UNIQUE(work_date, employee_name))''')
        conn.commit()
        conn.close()
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
    attrs = {
        "friendly_name": friendly, 
        "icon": icon, 
        "group": group, 
        "managed_by": "employee_manager"
    }
    if unit: attrs["unit_of_measurement"] = unit
    try:
        r = requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json={"state": str(state), "attributes": attrs})
        if r.status_code not in [200, 201]:
            log(f"Błąd (kod {r.status_code}) przy ustawianiu {entity_id}")
    except Exception as e:
        log(f"Wyjątek przy ustawianiu {entity_id}: {e}")

def save_report_to_db(work_counters):
    try:
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f: history = json.load(f)

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        snapshot = []
        emps = get_data() 
        for emp in emps:
            name = emp['name']
            safe_name = name.lower().replace(" ", "_")
            status = "Nieznany"
            sdata = get_state_full(f"sensor.{safe_name}_status")
            if sdata: status = sdata['state']
            
            work_time = 0.0
            if name in work_counters: work_time = round(work_counters[name], 1)
            
            snapshot.append({"name": name, "group": emp.get('group', 'Domyślna'), "status": status, "work_time": work_time})

        history.insert(0, {"id": int(time.time()), "date": timestamp, "entries": snapshot})
        if len(history) > 1000: history = history[:1000]

        with open(HISTORY_FILE, 'w') as f: json.dump(history, f, indent=4)
    except: pass

def main():
    wait_for_api()
    
    # === TUTAJ JEST ZMIANA - AUTOMATYCZNA INSTALACJA ===
    auto_install_card()
    # ===================================================

    log(f"=== START SYSTEMU LOGIKI ===")
    init_db()
    
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    work_counters = memory.get("counters", {})

    loop_counter = 0
    last_report_time = time.time()

    while True:
        try:
            current_time = time.time()
            if current_time - last_report_time >= 60:
                save_report_to_db(work_counters)
                last_report_time = current_time
            
            emps = get_data()
            loop_counter += 1
            should_save_db = False
            if loop_counter >= 6:
                should_save_db = True
                loop_counter = 0

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
                
                # Skanowanie czujników
                for eid in emp.get('sensors', []):
                    data = get_state_full(eid)
                    if not data: continue
                    state_val = data['state']
                    if state_val in ['unavailable', 'unknown', 'None']: continue
                    
                    attrs = data.get('attributes', {})
                    unit = attrs.get('unit_of_measurement')
                    
                    if unit == 'W' or unit == 'kW':
                        try:
                            val = float(state_val)
                            if unit == 'kW': val *= 1000
                            if val > 20.0: is_working = True
                        except: pass
                    elif eid.startswith("binary_sensor.") and state_val == 'on':
                        is_working = True
                    
                    suffix_info = None
                    if unit in UNIT_MAP: suffix_info = UNIT_MAP[unit]
                    
                    if suffix_info:
                        v_id = f"sensor.{safe}_{suffix_info['suffix']}"
                        set_state(v_id, state_val, f"{name} {suffix_info['suffix']}", suffix_info['icon'], group, unit)

                status = "Pracuje" if is_working else "Nieobecny"
                if is_working: work_counters[name] += (10/60)
                if is_working and should_save_db: log_minute_to_db(name)
                
                set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:laptop" if is_working else "mdi:account-off", group)
                set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", group, "min")

            memory["counters"] = work_counters
            save_status(memory)
            
        except Exception as e:
            log(f"Krytyczny błąd w pętli: {e}")

        time.sleep(10)

if __name__ == "__main__":
    main()