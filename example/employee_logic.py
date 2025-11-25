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

SENSOR_MAP = {
    "Temperatura": "sensor.light_sensor_temperatura",
    "Wilgotnosc": "sensor.light_sensor_wilgotnosc",
    "Cisnienie": "sensor.light_sensor_cisnienie"
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

def update_employee_sensor(name, label, value, unit, icon):
    safe_name = name.lower().replace(" ", "_")
    
    # Tworzymy sensor w HA
    entity_id = f"sensor.{safe_name}_wybrany_pomiar"
    
    state_data = {
        "state": value,
        "attributes": {
            "friendly_name": f"{name} - {label}",
            "unit_of_measurement": unit,
            "icon": icon
        }
    }
    requests.post(f"{API_URL}/states/{entity_id}", headers=HEADERS, json=state_data)

def main():
    log("Startuję logikę z listą wyboru...")

    while True:
        options = get_options()
        employees = options.get("employees", [])

        for emp in employees:
            name = emp['name']
            
            # 1. Pobieramy to, co wybrał User (np. "Temperatura")
            wybor_usera = emp.get('typ_pomiaru')
            
            # 2. Tłumaczymy to na ID sensora (z mapy na górze)
            real_sensor_id = SENSOR_MAP.get(wybor_usera)

            if not real_sensor_id:
                log(f"Nie znaleziono mapowania dla: {wybor_usera}")
                continue

            # 3. Pobieramy wartość z HA
            value = get_ha_state(real_sensor_id)
            
            # 4. Ustawiamy jednostki i ikony zależnie od wyboru (dla bajeru)
            unit = ""
            icon = "mdi:eye"
            
            if wybor_usera == "Temperatura":
                unit = "°C"
                icon = "mdi:thermometer"
            elif wybor_usera == "Wilgotnosc":
                unit = "%"
                icon = "mdi:water-percent"
            elif wybor_usera == "Cisnienie":
                unit = "hPa"
                icon = "mdi:gauge"

            # 5. Wysyłamy do HA
            if value:
                update_employee_sensor(name, wybor_usera, value, unit, icon)

        time.sleep(10)

if __name__ == "__main__":
    main()