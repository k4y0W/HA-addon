import json
import os
import logging
import requests
import csv
import io
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, Response
from employee_map import SENSOR_TYPES

DATA_FILE = "/data/employees.json"
GROUPS_FILE = "/data/groups.json"
OPTIONS_FILE = "/data/options.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
USER_TOKEN = ""

try:
    with open(OPTIONS_FILE, 'r') as f:
        opts = json.load(f)
        USER_TOKEN = opts.get("ha_token", "")
except:
    pass

API_URL = "http://supervisor/core/api"
HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    "Content-Type": "application/json",
}

app = Flask(__name__)

PRETTY_NAMES = {
    "temperature": "Temperatura",
    "humidity": "Wilgotność",
    "pressure": "Ciśnienie",
    "power": "Moc",
    "energy": "Energia",
    "voltage": "Napięcie",
    "current": "Natężenie",
    "battery": "Bateria",
    "signal_strength": "Sygnał",
    "pm25": "PM 2.5",
    "illuminance": "Jasność",
    "connectivity": "Połączenie"
}

BLOCKED_PREFIXES = [
    "sensor.backup_", "sensor.sun_", "sensor.date", "sensor.time", 
    "sensor.zone", "sensor.automation", "sensor.script", 
    "update.", "person.", "zone.", "sun.", "todo."
]
BLOCKED_DEVICE_CLASSES = ["timestamp", "enum", "update", "date"]
GENERATED_SUFFIXES = [
    "_status", "_czas_pracy", 
    "_temperatura", "_wilgotnosc", "_cisnienie", 
    "_moc", "_napiecie", "_natezenie", 
    "_pm25", "_bateria", "_jasnosc"
]

def load_json(file_path):
    if not os.path.exists(file_path):
        return []
    try:
        with open(file_path, 'r') as f:
            return json.load(f)
    except:
        return []

def save_json(file_path, data):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

def get_clean_sensors():
    sensors = []
    try:
        resp = requests.get(f"{API_URL}/states", headers=HEADERS)
        if resp.status_code == 200:
            all_states = resp.json()
            for entity in all_states:
                eid = entity['entity_id']
                attrs = entity.get("attributes", {})
                friendly_name = attrs.get("friendly_name", eid)
                device_class = attrs.get("device_class")
                
                if not (eid.startswith("sensor.") or eid.startswith("binary_sensor.") or eid.startswith("switch.") or eid.startswith("light.")): continue
                
                is_virtual = False
                for suffix in GENERATED_SUFFIXES:
                    if eid.endswith(suffix):
                        is_virtual = True
                        break
                if is_virtual: continue

                if " - " in friendly_name: continue

                if any(eid.startswith(prefix) for prefix in BLOCKED_PREFIXES): continue
                if device_class in BLOCKED_DEVICE_CLASSES: continue
                if "scene_history" in eid or "message" in eid: continue

                unit = attrs.get("unit_of_measurement", "")
                main_label = friendly_name 
                
                if device_class in PRETTY_NAMES: main_label = PRETTY_NAMES[device_class]
                elif unit == "W": main_label = "Moc"
                elif unit == "V": main_label = "Napięcie"
                elif unit == "kWh": main_label = "Energia"
                elif unit == "hPa": main_label = "Ciśnienie"
                elif unit == "%": main_label = "Wilgotność"
                
                sensors.append({
                    "id": eid,
                    "main_label": main_label,
                    "sub_label": friendly_name,
                    "unit": unit,
                    "state": entity.get("state", "-"),
                    "device_class": device_class
                })
            sensors.sort(key=lambda x: (x['main_label'], x['sub_label']))
    except:
        pass
    return sensors

def get_ha_state(entity_id):
    try:
        resp = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
        if resp.status_code == 200:
            state = resp.json().get("state")
            try:
                return str(round(float(state), 1))
            except:
                return state
    except:
        pass
    return "-"

HTML_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <style>
        /* ... (Style bez zmian) ... */
        .group-filters { overflow-x: auto; white-space: nowrap; padding-bottom: 10px; }
        .group-btn { border-radius: 20px; padding: 5px 15px; border: 1px solid #dee2e6; background: white; margin-right: 5px; color: #555; transition:0.2s; }
        .group-btn.active { background: var(--primary-color); color: white; border-color: var(--primary-color); }
    </style>
</head>
<body>
<div class="container" style="max-width: 1000px;">
    <div class="tab-content">
        <div class="tab-pane fade show active" id="pills-monitor">
            <div class="d-flex justify-content-between mb-3">
                <div class="group-filters d-flex" id="monitorFilters"></div> <a href="api/export_csv" target="_blank" class="btn btn-outline-dark btn-sm" style="white-space:nowrap"><i class="mdi mdi-file-excel"></i> CSV</a>
            </div>
            <div class="row g-3" id="grid"></div>
        </div>
        </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    const SENSORS = {{ all_sensors | tojson }};
    const ALL_GROUPS = {{ groups | tojson }}; /* KLUCZ: Wczytaj grupy od razu */
    
    let currentFilter = 'Wszyscy';
    let employeesCache = []; // Cache danych użytkowników

    // --- LOGIKA FILTRÓW ---
    function populateFilterBar() {
        const filters = document.getElementById('monitorFilters');
        filters.innerHTML = '';
        
        // 1. Przycisk "Wszyscy"
        let allBtn = document.createElement('button');
        allBtn.className = 'group-btn ' + (currentFilter === 'Wszyscy' ? 'active' : '');
        allBtn.innerText = 'Wszyscy';
        allBtn.addEventListener('click', () => filterMonitor('Wszyscy'));
        filters.appendChild(allBtn);
        
        // 2. Przyciski grup
        ALL_GROUPS.forEach(g => {
            if (g === 'Domyślna') return;
            let btn = document.createElement('button');
            btn.className = 'group-btn ' + (currentFilter === g ? 'active' : '');
            btn.innerText = g;
            btn.addEventListener('click', () => filterMonitor(g));
            filters.appendChild(btn);
        });
    }

    function filterMonitor(group) {
        currentFilter = group;
        populateFilterBar(); // Odśwież style przycisków
        renderGrid(); // Przerysuj listę
    }
    
    function renderGrid() {
        const grid = document.getElementById('grid');
        const filtered = currentFilter === 'Wszyscy' ? allEmployeesData : allEmployeesData.filter(e => e.group === currentFilter);
        
        if (filtered.length === 0) {
            grid.innerHTML = '<p class="text-center mt-5 text-muted">Brak pracowników w tej grupie.</p>';
            return;
        }
        
        // Tu logika renderowania kart (skrócone)
        grid.innerHTML = filtered.map(e => `
            <div class="col-md-6 col-xl-4"><div class="card h-100"><div class="card-body">... ${e.name} ...</div></div></div>
        `).join('');
    }

    // --- PRACOWNICY ---
    async function loadUsers() {
        const res = await fetch('api/employees');
        allEmployeesData = await res.json(); // Globalny cache danych
        renderGrid();
    }
    
    // --- INIT ---
    populateFilterBar();
    loadGroups();
    loadUsers();
    // ... (Reszta inicjalizacji i setInterval) ...
</script>
</body>
</html>
"""


@app.route('/')
def index():
    # Dane grup są wczytywane tu, aby były dostępne w szablonie JS
    groups = load_json(GROUPS_FILE)
    sensors = get_clean_sensors() # Użyj właściwej funkcji
    return render_template_string(HTML_PAGE, all_sensors=sensors, groups=groups)

@app.route('/api/groups', methods=['GET', 'POST'])
def handle_groups():
    grps = load_json(GROUPS_FILE)
    if not grps: grps = ["Domyślna"] # Zabezpieczenie na start
    if request.method == 'POST':
        name = request.json.get('name')
        if name and name not in grps: grps.append(name)
        save_json(GROUPS_FILE, grps)
    return jsonify(grps)

@app.route('/api/groups/<name>', methods=['DELETE'])
def del_group(name):
    if name == "Domyślna": return jsonify({"error": "Nie można usunąć domyślnej"}), 400
    grps = load_json(GROUPS_FILE)
    if name in grps: grps.remove(name)
    save_json(GROUPS_FILE, grps)
    # Przenieś pracowników do 'Domyślna'
    emps = load_json(DATA_FILE)
    for e in emps:
        if e.get('group') == name: e['group'] = "Domyślna"
    save_json(DATA_FILE, emps)
    return jsonify({"status":"ok"})

@app.route('/api/employees', methods=['GET'])
def api_get(): return jsonify(load_json(DATA_FILE))

@app.route('/api/employees', methods=['POST'])
def api_post():
    data = request.json
    emps = load_json(DATA_FILE)
    emps = [e for e in emps if e['name'] != data['name']]
    emps.append(data)
    save_json(DATA_FILE, emps)
    return jsonify({"status":"ok"})

@app.route('/api/employees/<int:i>', methods=['DELETE'])
def api_del(i):
    emps = load_json(DATA_FILE)
    if 0 <= i < len(emps): del emps[i]
    save_json(DATA_FILE, emps)
    return jsonify({"status":"ok"})

@app.route('/api/monitor', methods=['GET'])
def api_monitor():
    emps = load_json(DATA_FILE)
    res = []
    for emp in emps:
        safe = emp['name'].lower().replace(" ","_")
        status = get_ha_state(f"sensor.{safe}_status") or "N/A"
        time = get_ha_state(f"sensor.{safe}_czas_pracy") or "0"
        meas = []
        for entity_id in emp.get('sensors', []):
            val = get_ha_state(entity_id)
            try:
                r = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
                data = r.json()
                attrs = data['attributes']
                friendly_name = attrs.get('friendly_name', entity_id)
                dc = attrs.get('device_class')
                unit = attrs.get('unit_of_measurement', '')
                label = friendly_name
                if dc in PRETTY_NAMES: label = PRETTY_NAMES[dc]
                elif unit == "W": label = "Moc"
                elif unit == "V": label = "Napięcie"
                elif unit == "hPa": label = "Ciśnienie"
                elif unit == "%": label = "Wilgotność"
                meas.append({"label": label, "value": val, "unit": unit})
            except: pass
        res.append({"name": emp['name'], "status": status, "work_time": time, "measurements": meas})
    return jsonify(res)

@app.route('/api/export_csv')
def export_csv():
    import csv, io
    from datetime import datetime
    emps = load_json(DATA_FILE)
    si = io.StringIO(); cw = csv.writer(si, delimiter=';')
    cw.writerow(["Data", "Imie", "Grupa", "Status", "Czas (min)"])
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    for e in emps:
        safe = e['name'].lower().replace(" ", "_")
        status = get_ha_state(f"sensor.{safe}_status")
        time = get_ha_state(f"sensor.{safe}_czas_pracy")
        if time and '.' in time: time = time.replace('.', ',')
        cw.writerow([today, e['name'], e.get('group', ''), status, time])
    return Response(si.getvalue(), mimetype="text/csv", headers={"Content-disposition": f"attachment; filename=raport.csv"})