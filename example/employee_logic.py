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

# --- 🗺️ TWOJA MAPA URZĄDZEŃ (HARDCODED) ---
# Tu Ty, jako admin, przypisujesz techniczne ID do nazw z listy
STATION_MAP = {
    "Biurko Jana": {
        "power": "sensor.smart_plug_biezace_zuzycie",
        "motion": "binary_sensor.sonoff_snzb_06p"
    },
    "Biurko Marka": {
        "power": "sensor.gniazdko_marka_power",  # Zmień na prawdziwe ID!
        "motion": "binary_sensor.ruch_marka"      # Zmień na prawdziwe ID!
    },
    "Sala Konferencyjna": {
        "power": "sensor.tv_sala_power",
        "motion": "binary_sensor.ruch_sala"
    },
    "Kuchnia": {
        "power": "sensor.ekspres_do_kawy_power",
        "motion": None # Kuchnia może nie mieć czujnika ruchu
    }
}

def log(message):
    print(f"[EmployeeManager] {message}", flush=True)

def get_options():
    try:
        with open("/data/options.json", "r") as f:
            return json.load(f)
    except Exception as e:
        log(f"Error reading options: {e}")
        return {"employees": []}

def get_ha_state(entity_id):
    if not entity_id:
        return None
    try:
        url = f"{API_URL}/states/{entity_id}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            return data.get("state")
    except Exception as e:
        log(f"Error fetching {entity_id}: {e}")
    return None

def update_employee_sensor(name, status, work_time_minutes):
    safe_name = name.lower().replace(" ", "_")
    
    # Status
    requests.post(f"{API_URL}/states/sensor.{safe_name}_status", headers=HEADERS, json={
        "state": status,
        "attributes": {"friendly_name": f"{name} - Status", "icon": "mdi:account-tie"}
    })

    # Czas
    requests.post(f"{API_URL}/states/sensor.{safe_name}_czas_pracy", headers=HEADERS, json={
        "state": work_time_minutes,
        "attributes": {"friendly_name": f"{name} - Minuty Pracy", "unit_of_measurement": "min", "icon": "mdi:clock-outline"}
    })

def main():
    log("Startuję logikę ze sztywną mapą urządzeń...")
    work_counters = {} 

    while True:
        options = get_options()
        employees = options.get("employees", [])

        for emp in employees:
            name = emp['name']
            # Pobieramy to, co wybrał Kierownik z listy (np. "Biurko Jana")
            selected_station = emp.get('workstation')
            threshold = float(emp.get('threshold_watts', 10))

            if name not in work_counters:
                work_counters[name] = 0

            # --- 🔍 TŁUMACZENIE NAZWY NA ID ---
            station_data = STATION_MAP.get(selected_station)
            
            if not station_data:
                log(f"BŁĄD: Nie zdefiniowano mapy dla stanowiska: {selected_station}")
                update_employee_sensor(name, "Błąd Konfiguracji", 0)
                continue

            power_id = station_data.get("power")
            motion_id = station_data.get("motion")

            # --- LOGIKA ---
            status = "Nieznany"
            is_working = False

            # 1. Sprawdź Ruch (jeśli zdefiniowany)
            is_present = True
            if motion_id:
                motion_state = get_ha_state(motion_id)
                if motion_state != 'on':
                    is_present = False
                    status = "Poza Biurkiem"

            # 2. Sprawdź Prąd (tylko jeśli jest obecny)
            if is_present:
                current_power = get_ha_state(power_id)
                if current_power and current_power not in ["unavailable", "unknown"]:
                    try:
                        if float(current_power) > threshold:
                            status = "Pracuje"
                            is_working = True
                        else:
                            status = "Obecny (Idle)"
                    except ValueError:
                        status = "Błąd Odczytu"
                else:
                    status = "Brak Danych"

            if is_working:
                work_counters[name] += (10 / 60)

            update_employee_sensor(name, status, round(work_counters[name], 1))

        time.sleep(10)

if __name__ == "__main__":
    main()