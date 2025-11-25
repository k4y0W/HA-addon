SENSOR_TYPES = {
    "temperatura": {
        "label": "Temperatura",
        "unit": "°C",
        "icon": "mdi:thermometer",
        "device_class": "temperature"
    },
    "wilgotnosc": {
        "label": "Wilgotność",
        "unit": "%",
        "icon": "mdi:water-percent",
        "device_class": "humidity"
    },
    "cisnienie": {
        "label": "Ciśnienie",
        "unit": "hPa",
        "icon": "mdi:gauge",
        "device_class": "pressure"
    },
    "pm25": {
        "label": "Jakość Powietrza (PM2.5)",
        "unit": "μg/m³",
        "icon": "mdi:blur",
        "device_class": "pm25"
    },
    "bateria": {
        "label": "Bateria",
        "unit": "%",
        "icon": "mdi:battery",
        "device_class": "battery"
    },
    "moc": {
        "label": "Moc",
        "unit": "W",
        "icon": "mdi:lightning-bolt",
        "device_class": "power"
    },
    "napiecie": {
        "label": "Napięcie",
        "unit": "V",
        "icon": "mdi:sine-wave",
        "device_class": "voltage"
    }
}

SENSOR_MAP = SENSOR_TYPES