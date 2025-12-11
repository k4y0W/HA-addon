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
SOURCE_JS_FILE = "/app/employee-card.js"
HA_WWW_DIR = "/config/www"
DEST_JS_FILE = os.path.join(HA_WWW_DIR, "employee-card.js")
CARD_URL_RESOURCE = "/local/employee-card.js"

# --- KONFIGURACJA API I TOKENA ---
TOKEN = ""
API_URL = ""

try:
    if os.path.exists(OPTIONS_FILE):
        with open(OPTIONS_FILE, 'r') as f:
            opts = json.load(f)
            TOKEN = opts.get("ha_token", "").strip()
except:
    pass

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
    log(f"Sprawdzanie połączenia z API: {API_URL} ...")
    while True:
        try:
            r = requests.get(f"{API_URL}/", headers=HEADERS, timeout=5)
            if r.status_code in [200, 201, 401, 404, 405]:
                log(">>> POŁĄCZENIE NAWIĄZANE! Startuję logikę sensorów. <<<")
                return
        except Exception:
            pass
        time.sleep(10)

def auto_install_card():
    try:
        if not os.path.exists(HA_WWW_DIR): os.makedirs(HA_WWW_DIR)
        shutil.copy(SOURCE_JS_FILE, DEST_JS_FILE)
    except: pass
    
    try:
        url = f"{API_URL}/lovelace/resources"
        get_resp = requests.get(url, headers=HEADERS)
        if get_resp.status_code == 200:
            for res in get_resp.json():
                if res['url'] == CARD_URL_RESOURCE: return
        
        requests.post(url, headers=HEADERS, json={"url": CARD_URL_RESOURCE, "type": "module"})
    except: pass

def init_db():
    try:
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS work_history
                     (work_date TEXT, employee_name TEXT, minutes_worked INTEGER, 
                     UNIQUE(work_date, employee_name))''')
        conn.commit()
        conn.close()
    except: pass

def log_minute_to_db(employee_name):
    try:
        today = datetime.now().strftime("%Y-%m-%d")
        conn = sqlite3.connect(DB_FILE)
        c = conn.cursor()
        try:
            c.execute("INSERT INTO work_history (work_date, employee_name, minutes_worked) VALUES (?, ?, 1)", (today, employee_name))
        except sqlite3.IntegrityError:
            c.execute("UPDATE work_history SET minutes_worked = minutes_worked + 1 WHERE work_date=? AND employee_name=?", (today, employee_name))
        conn.commit()
        conn.close()
    except: pass

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
        if r.status_code == 200: return r.json()
    except: pass
    return None

def set_state(entity_id, state, friendly, icon, group, unit=None):
    attrs = {"friendly_name": friendly, "icon": icon, "group": group, "managed_by": "employee_manager"}
    if unit: attrs["unit_of_measurement"] = unit
    try: requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json={"state": str(state), "attributes": attrs})
    except: pass

# --- NOWA FUNKCJA RAPORTOWANIA (ANALIZA GRUP I SORTOWANIE) ---
def save_daily_report(work_counters, report_date):
    try:
        log(f">>> Generowanie raportu dobowego za {report_date}...")
        history = []
        if os.path.exists(HISTORY_FILE):
            with open(HISTORY_FILE, 'r') as f: history = json.load(f)

        timestamp = f"{report_date} (Raport Dobowy)"
        snapshot = []
        
        # Słownik do analizy grup (Pomieszczeń)
        groups_analysis = {}

        emps = get_data() 
        for emp in emps:
            name = emp['name']
            group = emp.get('group', 'Domyślna')
            
            # Pobieranie czasu pracy
            work_time = 0.0
            if name in work_counters: work_time = round(work_counters[name], 1)
            
            snapshot.append({
                "name": name, 
                "group": group, 
                "work_time": work_time
            })

            # Analiza Grupowa
            if group not in groups_analysis:
                groups_analysis[group] = {"total_minutes": 0, "people_count": 0}
            
            groups_analysis[group]["total_minutes"] += work_time
            groups_analysis[group]["people_count"] += 1

        # 1. SORTOWANIE: Najpierw Grupa A-Z, potem Imię A-Z
        snapshot.sort(key=lambda x: (x['group'], x['name']))

        # 2. PRZYGOTOWANIE ANALIZY GRUP DO ZAPISU
        groups_summary = []
        for g_name, stats in groups_analysis.items():
            hours = round(stats["total_minutes"] / 60, 1)
            groups_summary.append({
                "group": g_name,
                "total_hours": hours,
                "avg_per_person": round(stats["total_minutes"] / stats["people_count"], 1) if stats["people_count"] > 0 else 0
            })
        
        # Sortowanie analizy grup
        groups_summary.sort(key=lambda x: x['group'])

        # Zapis do historii
        history.insert(0, {
            "id": int(time.time()), 
            "date": timestamp, 
            "entries": snapshot,
            "group_summary": groups_summary # Dodajemy sekcję analizy
        })
        
        if len(history) > 365: history = history[:365] # Trzymamy rok

        with open(HISTORY_FILE, 'w') as f: json.dump(history, f, indent=4)
        log(">>> Raport dobowy zapisany.")
    except Exception as e:
        log(f"Błąd zapisu raportu: {e}")

def main():
    wait_for_api()
    auto_install_card()
    log(f"=== START SYSTEMU LOGIKI ===")
    init_db()
    
    memory = load_status()
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # Jeśli system wstał w nowy dzień, resetujemy liczniki (zakładamy że raport zrobił się wczoraj lub przepadł)
    if memory.get("date") != today_str:
        memory = {"date": today_str, "counters": {}}
    
    work_counters = memory.get("counters", {})
    last_loop_date = today_str

    while True:
        try:
            current_date = datetime.now().strftime("%Y-%m-%d")
            
            # --- RAPORTOWANIE O PÓŁNOCY ---
            # Jeśli data w pętli różni się od daty ostatniego obiegu, to znaczy, że minęła północ.
            # Zapisujemy raport za POPRZEDNI dzień i resetujemy liczniki.
            if current_date != last_loop_date:
                save_daily_report(work_counters, last_loop_date)
                
                # Reset na nowy dzień
                work_counters = {}
                memory["date"] = current_date
                memory["counters"] = {}
                save_status(memory)
                last_loop_date = current_date
            # ------------------------------

            emps = get_data()
            group_stats = {} 

            for emp in emps:
                name = emp['name'].strip()
                safe = name.lower().replace(" ", "_")
                group = emp.get('group', 'Domyślna')

                if group not in group_stats:
                    group_stats[group] = {"active_count": 0, "total_power": 0.0, "temps": [], "humidities": []}

                if name not in work_counters: work_counters[name] = 0.0
                is_working = False
                
                for eid in emp.get('sensors', []):
                    data = get_state_full(eid)
                    if not data: continue
                    state_val = data['state']
                    if state_val in ['unavailable', 'unknown', 'None']: continue
                    
                    attrs = data.get('attributes', {})
                    unit = attrs.get('unit_of_measurement')
                    
                    try:
                        f_val = float(state_val)
                        if unit == '°C': group_stats[group]["temps"].append(f_val)
                        elif unit == '%': group_stats[group]["humidities"].append(f_val)
                        elif unit == 'W':
                            group_stats[group]["total_power"] += f_val
                            if f_val > 20.0: is_working = True
                        elif unit == 'kW':
                            group_stats[group]["total_power"] += (f_val * 1000)
                            if (f_val * 1000) > 20.0: is_working = True
                    except: pass

                    if eid.startswith("binary_sensor.") and state_val == 'on': is_working = True
                    
                    suffix_info = None
                    if unit in UNIT_MAP: suffix_info = UNIT_MAP[unit]
                    if suffix_info:
                        set_state(f"sensor.{safe}_{suffix_info['suffix']}", state_val, f"{name} {suffix_info['suffix']}", suffix_info['icon'], group, unit)

                status = "Pracuje" if is_working else "Nieobecny"
                if is_working: 
                    work_counters[name] += (10/60)
                    group_stats[group]["active_count"] += 1
                    log_minute_to_db(name) # Baza SQL wciąż zbiera co minutę dla bezpieczeństwa
                
                set_state(f"sensor.{safe}_status", status, f"{name} - Status", "mdi:laptop" if is_working else "mdi:account-off", group)
                set_state(f"sensor.{safe}_czas_pracy", round(work_counters[name], 1), f"{name} - Czas", "mdi:clock", group, "min")

            # Tworzenie sensorów grupowych
            for grp_name, stats in group_stats.items():
                if grp_name == "Domyślna": continue
                safe_grp = grp_name.lower().replace(" ", "_")
                
                set_state(f"binary_sensor.grupa_{safe_grp}_zajetosc", "on" if stats["active_count"] > 0 else "off", f"Pomieszczenie {grp_name}", "mdi:account-group", grp_name)
                
                if stats["total_power"] > 0:
                    set_state(f"sensor.grupa_{safe_grp}_moc", round(stats["total_power"], 1), f"{grp_name} - Moc", "mdi:lightning-bolt", grp_name, "W")
                if len(stats["temps"]) > 0:
                    avg_temp = sum(stats["temps"]) / len(stats["temps"])
                    set_state(f"sensor.grupa_{safe_grp}_temperatura", round(avg_temp, 1), f"{grp_name} - Temp", "mdi:thermometer", grp_name, "°C")

            memory["counters"] = work_counters
            save_status(memory)
            
        except Exception as e:
            log(f"Krytyczny błąd w pętli: {e}")

        time.sleep(10)

if __name__ == "__main__":
    main()