import os
import time
import requests
import json
import sys
from employee_map import SENSOR_MAP # Import mapy

SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
API_URL = "http://supervisor/core/api"
HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    "Content-Type": "application/json",
}
DATA_FILE = "/data/employees.json"

def log(message):
    print(f"[EmployeeLogic] {message}", flush=True)

def get_employees_from_db():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def get_ha_state(entity_id):
    if not entity_id: return None
    try:
        url = f"{API_URL}/states/{entity_id}"
        response = requests.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json().get("state")
    except:
        pass
    return None

def update_sensor(safe_name, suffix, value, friendly_name, unit, icon):
    entity_id = f"sensor.{safe_name}_{suffix}"
    payload = {
        "state": value,
        "attributes": {
            "friendly_name": friendly_name,
            "unit_of_measurement": unit,
            "icon": icon
        }
    }
    requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json=payload)

def main():
    log("Startuję logikę opartą o bazę danych JSON...")

    while True:
        employees = get_employees_from_db()

        for emp in employees:
            name = emp['name']
            assigned_sensors = emp.get('sensors', [])
            safe_name = name.lower().replace(" ", "_")

            # Dla każdego przypisanego czujnika (np. Temperatura, Wilgotnosc)
            for sensor_human_name in assigned_sensors:
                
                # Pobierz dane techniczne z mapy
                sensor_def = SENSOR_MAP.get(sensor_human_name)
                if not sensor_def: continue

                real_id = sensor_def['entity_id']
                val = get_ha_state(real_id)

                if val:
                    # Tworzymy encję w HA: sensor.jan_temperatura
                    suffix = sensor_human_name.lower()
                    friendly = f"{name} - {sensor_human_name}"
                    
                    update_sensor(safe_name, suffix, val, friendly, sensor_def['unit'], sensor_def['icon'])

        time.sleep(10)

if __name__ == "__main__":
    main()