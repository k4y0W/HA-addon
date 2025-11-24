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
    try:
        url = f"{API_URL}/states/{entity_id}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            data = response.json()
            return data.get("state")
        else:
            log(f"API Error GET {entity_id}: Status {response.status_code}")
    except Exception as e:
        log(f"Error fetching {entity_id}: {e}")
    return None

def update_employee_sensor(name, status, work_time_minutes):
    safe_name = name.lower().replace(" ", "_")
    
    entity_id_status = f"sensor.{safe_name}_status"
    state_data = {
        "state": status,
        "attributes": {
            "friendly_name": f"{name} - Status",
            "icon": "mdi:account-tie"
        }
    }
    response_status = requests.post(f"{API_URL}/states/{entity_id_status}", headers=HEADERS, json=state_data)
    if response_status.status_code not in [200, 201]:
        log(f"API Error POST Status Sensor: Status {response_status.status_code} - {response_status.text}")

    entity_id_time = f"sensor.{safe_name}_czas_pracy"
    state_data_time = {
        "state": work_time_minutes,
        "attributes": {
            "friendly_name": f"{name} - Minuty Pracy Dzis",
            "unit_of_measurement": "min",
            "icon": "mdi:clock-outline"
        }
    }
    response_time = requests.post(f"{API_URL}/states/{entity_id_time}", headers=HEADERS, json=state_data_time)
    if response_time.status_code not in [200, 201]:
        log(f"API Error POST Time Sensor: Status {response_time.status_code} - {response_time.text}")

def main():
    log("Starting logic...")
    
    work_counters = {} 

    while True:
        options = get_options()
        employees = options.get("employees", [])

        if not employees:
            log("Brak skonfigurowanych pracowników. Czekam na konfigurację...")
        
        for emp in employees:
            name = emp['name']
            power_sensor = emp['power_sensor']
            threshold = float(emp.get('threshold_watts', 10))

            if name not in work_counters:
                work_counters[name] = 0

            current_power = get_ha_state(power_sensor)
            
            status = "Nieobecny"
            is_working = False

            if current_power and current_power != "unavailable" and current_power != "unknown":
                try:
                    watts = float(current_power)
                    if watts > threshold:
                        status = "Pracuje"
                        is_working = True
                    else:
                        status = "Obecny (Idle)"
                except ValueError:
                    status = "Blad Danych"
            
            if is_working:
                work_counters[name] += (10 / 60)

            update_employee_sensor(name, status, round(work_counters[name], 1))

        time.sleep(10)

if __name__ == "__main__":
    main()