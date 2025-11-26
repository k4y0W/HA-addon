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
OPTIONS_FILE = "/data/options.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
USER_TOKEN = ""

try:
    with open(OPTIONS_FILE, 'r') as f:
        opts = json.load(f)
        USER_TOKEN = opts.get("ha_token", "")
except: pass

API_URL = "http://supervisor/core/api"
HEADERS = {"Authorization": f"Bearer {SUPERVISOR_TOKEN}", "Content-Type": "application/json"}

app = Flask(__name__)

# --- KONFIGURACJA SENSORÓW (Skopiuj ze starego pliku lub zostaw te) ---
PRETTY_NAMES = { "temperature": "Temperatura", "humidity": "Wilgotność", "pressure": "Ciśnienie", "power": "Moc", "energy": "Energia", "voltage": "Napięcie", "current": "Natężenie", "battery": "Bateria", "signal_strength": "Sygnał", "pm25": "PM 2.5", "illuminance": "Jasność", "connectivity": "Połączenie" }
BLOCKED_PREFIXES = ["sensor.backup_", "sensor.sun_", "sensor.date", "sensor.time", "sensor.zone", "sensor.automation", "sensor.script", "update.", "person.", "zone.", "sun.", "todo."]
BLOCKED_DEVICE_CLASSES = ["timestamp", "enum", "update", "date"]
GENERATED_SUFFIXES = ["_status", "_czas_pracy", "_temperatura", "_wilgotnosc", "_cisnienie", "_moc", "_napiecie", "_natezenie", "_pm25", "_bateria", "_jasnosc"]

# --- FUNKCJE POMOCNICZE ---
def load_employees():
    if not os.path.exists(DATA_FILE): return []
    try: with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def save_employees(data):
    with open(DATA_FILE, 'w') as f: json.dump(data, f, indent=4)

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
                
                # Filtrowanie
                is_virtual = False
                for suffix in GENERATED_SUFFIXES:
                    if eid.endswith(suffix) and " - " in friendly_name: is_virtual = True; break
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
                elif unit == "hPa": main_label = "Ciśnienie"
                elif unit == "%": main_label = "Wilgotność"
                
                sensors.append({"id": eid, "main_label": main_label, "sub_label": friendly_name, "unit": unit, "state": entity.get("state", "-"), "device_class": device_class})
            sensors.sort(key=lambda x: (x['main_label'], x['sub_label']))
    except: pass
    return sensors

def get_ha_state(entity_id):
    try:
        resp = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
        if resp.status_code == 200:
            state = resp.json().get("state")
            try: return str(round(float(state), 1))
            except: return state
    except: pass
    return "-"

# --- NOWA FUNKCJA INSTALACJI (MULTI-CARD) ---
def register_lovelace_resource():
    # Lista kart do zainstalowania
    CARDS_TO_INSTALL = [
        "/local/employee-card.js",
        "/local/community_cards/auto-entities.js",
        "/local/community_cards/apexcharts-card.js"
    ]

    token_to_use = USER_TOKEN if USER_TOKEN else SUPERVISOR_TOKEN
    install_headers = {"Authorization": f"Bearer {token_to_use}", "Content-Type": "application/json"}
    
    log = []
    try:
        # 1. Pobierz listę obecnych zasobów
        get_resp = requests.get(f"{API_URL}/lovelace/resources", headers=install_headers)
        if get_resp.status_code in [401, 403, 404]: return False, "Brak uprawnień! Podaj Token."
        
        existing_urls = [r['url'] for r in get_resp.json()]

        # 2. Pętla po kartach
        for card_url in CARDS_TO_INSTALL:
            if card_url in existing_urls:
                log.append(f"OK: {card_url.split('/')[-1]}")
            else:
                # Dodaj nową
                payload = {"url": card_url, "type": "module"}
                post_resp = requests.post(f"{API_URL}/lovelace/resources", headers=install_headers, json=payload)
                if post_resp.status_code in [200, 201]: 
                    log.append(f"DODANO: {card_url.split('/')[-1]}")
                else: 
                    log.append(f"BŁĄD: {card_url.split('/')[-1]}")

        return True, " | ".join(log)

    except Exception as e: return False, str(e)


# --- HTML ---
HTML_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Employee Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/@mdi/font/css/materialdesignicons.min.css" rel="stylesheet">
    <style>body { background-color: #f8f9fa; padding: 20px; font-family: 'Segoe UI', sans-serif; }</style>
</head>
<body>
<div class="container" style="max-width: 1000px;">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3 class="fw-bold text-primary"><i class="mdi mdi-account-group"></i> Employee Manager</h3>
        <ul class="nav nav-pills bg-white p-1 rounded shadow-sm">
            <li class="nav-item"><button class="nav-link active" id="tab-monitor" data-bs-toggle="pill" data-bs-target="#pills-monitor">Monitor</button></li>
            <li class="nav-item"><button class="nav-link" id="tab-config" data-bs-toggle="pill" data-bs-target="#pills-config">Konfiguracja</button></li>
            <li class="nav-item"><button class="nav-link text-success fw-bold" id="tab-install" onclick="installCard()"><i class="mdi mdi-download"></i> Instaluj Karty</button></li>
        </ul>
    </div>

    <div class="tab-content">
        <div class="tab-pane fade show active" id="pills-monitor">
            <div class="d-flex justify-content-end mb-3">
                <a href="api/export_csv" target="_blank" class="btn btn-outline-dark btn-sm"><i class="mdi mdi-file-excel"></i> Pobierz Raport (CSV)</a>
            </div>
            <div class="row g-3" id="dashboard-grid"></div>
        </div>

        <div class="tab-pane fade" id="pills-config">
            <div class="row">
                <div class="col-lg-7">
                    <div class="card shadow-sm mb-4">
                        <div class="card-header bg-white fw-bold">Dodaj / Edytuj</div>
                        <div class="card-body">
                            <form id="addForm">
                                <div class="mb-3"><label class="form-label fw-bold">Imię</label><input type="text" class="form-control" id="empName" required placeholder="np. Jan"></div>
                                <div class="mb-3"><label class="form-label fw-bold d-flex justify-content-between"><span>Przypisz Czujniki</span><span class="badge bg-light text-dark fw-normal border" id="count-badge">0 wybranych</span></label><input type="text" class="form-control form-control-sm mb-2" id="sensorSearch" placeholder="🔍 Filtruj..."><div class="sensor-list-container border rounded p-2 bg-light" style="max-height: 400px; overflow-y: auto;"><div id="sensorList" class="d-flex flex-column gap-2"><div class="text-center text-muted p-3">Ładowanie...</div></div></div></div>
                                <button type="submit" class="btn btn-primary w-100">Zapisz</button>
                            </form>
                        </div>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="card shadow-sm">
                        <div class="card-header bg-white fw-bold">Lista Pracowników</div>
                        <div class="card-body p-0"><table class="table table-hover mb-0 align-middle"><tbody id="configTable"></tbody></table></div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="modal fade" id="installModal" tabindex="-1">
  <div class="modal-dialog"><div class="modal-content"><div class="modal-header bg-light"><h5 class="modal-title">Instalacja Kart</h5><button type="button" class="btn-close" data-bs-dismiss="modal"></button></div>
  <div class="modal-body">
    <p>Automatyczna instalacja zablokowana. Dodaj te linki ręcznie w zasobach:</p>
    <ul class="list-group mb-3">
        <li class="list-group-item user-select-all">/local/employee-card.js</li>
        <li class="list-group-item user-select-all">/config/www/community_cards/auto-entities.js</li>
        <li class="list-group-item user-select-all">/config/www/community_cards/apexcharts-card.js</li>
    </ul>
    <a href="/config/lovelace/resources" target="_blank" class="btn btn-success w-100">Otwórz Ustawienia Zasobów</a>
  </div></div></div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    const ALL_SENSORS = {{ all_sensors | tojson }};
    const chkContainer = document.getElementById('sensorList');
    const countBadge = document.getElementById('count-badge');
    const installModal = new bootstrap.Modal(document.getElementById('installModal'));

    function updateCount() { countBadge.innerText = document.querySelectorAll('#sensorList input:checked').length + " wybranych"; }

    async function installCard() {
        const btn = document.getElementById('tab-install');
        btn.innerHTML = '⏳ Instaluję 3 karty...';
        try {
            const res = await fetch('api/install_card', { method: 'POST' });
            const data = await res.json();
            if(data.success) alert("SUKCES! " + data.message + "\\n\\nOdśwież stronę (Ctrl+F5)!");
            else installModal.show();
        } catch (e) { installModal.show(); }
        btn.innerHTML = '<i class="mdi mdi-download"></i> Instaluj Karty';
    }

    // ... (RESZTA JS BEZ ZMIAN - renderSensorList, refreshMonitor, loadConfig, addForm, del) ...
    function renderSensorList(f = "") {
        chkContainer.innerHTML = "";
        ALL_SENSORS.forEach(s => {
            if(f && !s.name.toLowerCase().includes(f.toLowerCase())) return;
            const d = document.createElement('div'); d.className = 'sensor-tile rounded p-2 d-flex align-items-center';
            let icon="mdi-eye"; if(s.main_label=="Temperatura") icon="mdi-thermometer"; else if(s.main_label=="Moc") icon="mdi-lightning-bolt";
            d.innerHTML = `<div class="me-3 d-flex align-items-center justify-content-center bg-light rounded-circle" style="width:36px;height:36px;"><i class="mdi ${icon} fs-5 text-secondary"></i></div><div style="flex:1"><div class="tile-header text-truncate">${s.main_label}</div><div class="tile-sub text-truncate">${s.sub_label}</div></div><div class="tile-val">${s.state} ${s.unit}</div><input class="form-check-input d-none" type="checkbox" value="${s.id}" id="chk_${s.id}">`;
            d.addEventListener('click', ()=>{ const i=d.querySelector('input'); i.checked=!i.checked; if(i.checked) d.classList.add('selected'); else d.classList.remove('selected'); updateCount(); });
            chkContainer.appendChild(d);
        });
    }
    document.getElementById('sensorSearch').addEventListener('input', (e) => renderSensorList(e.target.value));
    async function refreshMonitor() {
        if (!document.getElementById('tab-monitor').classList.contains('active')) return;
        const res = await fetch('api/monitor'); const data = await res.json();
        const g = document.getElementById('dashboard-grid'); g.innerHTML = data.map(e => `<div class="col-md-6 col-xl-4"><div class="card h-100"><div class="card-body"><div class="d-flex align-items-center mb-3"><div class="bg-light p-3 rounded-circle me-3"><i class="mdi mdi-account fs-3"></i></div><div><h5 class="mb-0 fw-bold">${e.name}</h5><small>● ${e.status}</small></div><div class="ms-auto text-end"><div class="fs-4 fw-bold">${e.work_time}</div><div class="small">MIN</div></div></div><div class="row g-2">${e.measurements.map(m=>`<div class="col-6"><div class="p-2 border rounded bg-light text-center"><small>${m.label}</small><strong>${m.value} ${m.unit}</strong></div></div>`).join('')}</div></div></div></div>`).join('');
    }
    async function loadConfig() {
        const res = await fetch('api/employees'); const data = await res.json();
        document.getElementById('configTable').innerHTML = data.map((e,i) => `<tr><td><strong>${e.name}</strong></td><td><span class="badge bg-secondary">${e.sensors?e.sensors.length:0}</span></td><td class="text-end"><button class="btn btn-sm btn-outline-danger" onclick="del(${i})">Usuń</button></td></tr>`).join('');
    }
    document.getElementById('addForm').onsubmit = async (e) => {
        e.preventDefault(); const n = document.getElementById('empName').value; const s = [];
        document.querySelectorAll('#sensorList input:checked').forEach(c => s.push(c.value));
        await fetch('api/employees', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name:n, sensors:s}) });
        document.getElementById('empName').value=''; renderSensorList(); loadConfig(); refreshMonitor(); alert('Zapisano!');
    };
    window.del = async (i) => { if(confirm("Usunąć?")) { await fetch('api/employees/'+i, { method:'DELETE' }); loadConfig(); refreshMonitor(); } }
    renderSensorList(); loadConfig(); refreshMonitor(); setInterval(refreshMonitor, 3000);
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE, all_sensors=get_clean_sensors())

# Endpointy API (bez zmian)
@app.route('/api/export_csv')
def export_csv():
    import csv, io
    from datetime import datetime
    emps = load_employees()
    si = io.StringIO(); cw = csv.writer(si, delimiter=';')
    cw.writerow(["Data", "Imie", "Status", "Czas (min)"])
    today = datetime.now().strftime("%Y-%m-%d %H:%M")
    for e in emps:
        safe = e['name'].lower().replace(" ", "_")
        status = get_ha_state(f"sensor.{safe}_status")
        time = get_ha_state(f"sensor.{safe}_czas_pracy")
        if time and '.' in time: time = time.replace('.', ',')
        cw.writerow([today, e['name'], status, time])
    return Response(si.getvalue(), mimetype="text/csv", headers={"Content-disposition": f"attachment; filename=raport.csv"})
@app.route('/api/employees', methods=['GET'])
def api_get(): return jsonify(load_employees())
@app.route('/api/employees', methods=['POST'])
def api_post():
    data = request.json
    emps = load_employees()
    emps = [e for e in emps if e['name'] != data['name']]
    emps.append(data)
    save_employees(emps)
    return jsonify({"status":"ok"})
@app.route('/api/employees/<int:i>', methods=['DELETE'])
def api_del(i):
    emps = load_employees()
    if 0 <= i < len(emps): del emps[i]
    save_employees(emps)
    return jsonify({"status":"ok"})
@app.route('/api/monitor', methods=['GET'])
def api_monitor():
    emps = load_employees()
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
                meas.append({"label": label, "value": val, "unit": unit})
            except: pass
        res.append({"name": emp['name'], "status": status, "work_time": time, "measurements": meas})
    return jsonify(res)
@app.route('/api/install_card', methods=['POST'])
def api_install_card():
    success, msg = register_lovelace_resource()
    return jsonify({"success": success, "message": msg})