import json
import os
import logging
import requests
from flask import Flask, request, jsonify, render_template_string

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
    "illuminance": "Jasność"
}

BLOCKED_PREFIXES = ["sensor.backup_", "sensor.sun_", "sensor.date", "sensor.time", "sensor.zone", "sensor.automation", "sensor.script", "update.", "person.", "zone.", "sun."]
BLOCKED_DEVICE_CLASSES = ["timestamp", "enum", "update", "date"]

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
                if eid.endswith("_status") or eid.endswith("_czas_pracy") or "_wybrany_pomiar" in eid: continue
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

def register_lovelace_resource():
    CARD_URL = "/local/employee-card.js"
    token_to_use = USER_TOKEN if USER_TOKEN else SUPERVISOR_TOKEN
    install_headers = {"Authorization": f"Bearer {token_to_use}", "Content-Type": "application/json"}
    try:
        # Próba 1: Przez Supervisor Proxy
        url = f"{API_URL}/lovelace/resources"
        
        # Próba 2: Jeśli user podał token, spróbujmy bezpośrednio do localhost (ominięcie proxy Supervisora)
        if USER_TOKEN:
            # Często HA w kontenerach jest dostępny pod tym adresem
            # url = "http://homeassistant:8123/api/lovelace/resources" 
            pass 

        get_resp = requests.get(url, headers=install_headers)
        if get_resp.status_code in [401, 403, 404]: return False, "Brak uprawnień API."
        
        resources = get_resp.json()
        for res in resources:
            if res['url'] == CARD_URL: return True, "Zasób już istnieje!"

        payload = {"url": CARD_URL, "type": "module"}
        post_resp = requests.post(url, headers=install_headers, json=payload)
        
        if post_resp.status_code in [200, 201]: return True, "Dodano kartę!"
        else: return False, f"Błąd API: {post_resp.text}"
    except Exception as e: return False, str(e)


HTML_PAGE = """
<!DOCTYPE html>
<html lang="pl">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>Employee Manager</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link href="https://cdn.jsdelivr.net/npm/@mdi/font/css/materialdesignicons.min.css" rel="stylesheet">
    <style>
        body { background-color: #f8f9fa; padding: 20px; font-family: 'Segoe UI', sans-serif; }
        .sensor-tile { cursor: pointer; transition: all 0.2s; border: 1px solid #dee2e6; background: white; position: relative; overflow: hidden; }
        .sensor-tile:hover { background-color: #f1f3f5; border-color: #adb5bd; }
        .sensor-tile.selected { border-color: #0d6efd; background-color: #e7f1ff; box-shadow: 0 0 0 1px #0d6efd; }
        .tile-header { font-weight: bold; color: #333; font-size: 0.95rem; }
        .tile-sub { font-size: 0.75rem; color: #888; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .tile-val { font-size: 0.85rem; font-weight: 600; color: #0d6efd; margin-left: auto; }
        .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 6px; }
        .bg-working { background-color: #28a745; } .bg-idle { background-color: #ffc107; } .bg-absent { background-color: #dc3545; }
    </style>
</head>
<body>

<div class="container" style="max-width: 1000px;">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3 class="fw-bold text-primary"><i class="mdi mdi-account-group"></i> Employee Manager</h3>
        <ul class="nav nav-pills bg-white p-1 rounded shadow-sm">
            <li class="nav-item"><button class="nav-link active" id="tab-monitor" data-bs-toggle="pill" data-bs-target="#pills-monitor">Monitor</button></li>
            <li class="nav-item"><button class="nav-link" id="tab-config" data-bs-toggle="pill" data-bs-target="#pills-config">Konfiguracja</button></li>
            <li class="nav-item"><button class="nav-link text-success fw-bold" id="tab-install" onclick="installCard()"><i class="mdi mdi-download"></i> Zainstaluj Kartę</button></li>
        </ul>
    </div>

    <div class="tab-content">
        <div class="tab-pane fade show active" id="pills-monitor"><div class="row g-3" id="dashboard-grid"></div></div>
        <div class="tab-pane fade" id="pills-config">
            <div class="row">
                <div class="col-lg-7">
                    <div class="card shadow-sm mb-4">
                        <div class="card-header bg-white fw-bold">Dodaj / Edytuj</div>
                        <div class="card-body">
                            <form id="addForm">
                                <div class="mb-3">
                                    <label class="form-label fw-bold">Imię i Nazwisko</label>
                                    <input type="text" class="form-control" id="empName" required placeholder="np. Jan Kowalski">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label fw-bold d-flex justify-content-between">
                                        <span>Przypisz Czujniki</span>
                                        <span class="badge bg-light text-dark fw-normal border" id="count-badge">0 wybranych</span>
                                    </label>
                                    <input type="text" class="form-control form-control-sm mb-2" id="sensorSearch" placeholder="🔍 Filtruj...">
                                    <div class="sensor-list-container border rounded p-2 bg-light" style="max-height: 400px; overflow-y: auto;">
                                        <div id="sensorList" class="d-flex flex-column gap-2"><div class="text-center text-muted p-3">Ładowanie...</div></div>
                                    </div>
                                </div>
                                <button type="submit" class="btn btn-primary w-100">Zapisz Pracownika</button>
                            </form>
                        </div>
                    </div>
                </div>
                <div class="col-lg-5">
                    <div class="card shadow-sm">
                        <div class="card-header bg-white fw-bold">Lista Pracowników</div>
                        <div class="card-body p-0">
                            <table class="table table-hover mb-0 align-middle"><thead class="table-light"><tr><th>Imię</th><th>Liczba</th><th></th></tr></thead><tbody id="configTable"></tbody></table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="modal fade" id="installModal" tabindex="-1">
  <div class="modal-dialog">
    <div class="modal-content">
      <div class="modal-header bg-light">
        <h5 class="modal-title">Konfiguracja Karty</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body text-center">
        <div class="mb-3">
             <i class="mdi mdi-clipboard-check text-success" style="font-size: 4rem;"></i>
             <h5>Link skopiowany do schowka!</h5>
        </div>
        <p class="text-muted">Automatyczna instalacja została zablokowana przez HA.<br>Ale spokojnie, link masz już w schowku:</p>
        <div class="alert alert-secondary p-2 user-select-all" id="link-box">/local/employee-card.js</div>
        <hr>
        <p class="mb-2">Teraz kliknij przycisk poniżej, aby otworzyć ustawienia Zasobów i wklej link (CTRL+V).</p>
        <a href="/config/lovelace/resources" target="_blank" class="btn btn-primary w-100"><i class="mdi mdi-open-in-new"></i> Otwórz Ustawienia Zasobów</a>
      </div>
    </div>
  </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    const ALL_SENSORS = {{ all_sensors | tojson }};
    const chkContainer = document.getElementById('sensorList');
    const countBadge = document.getElementById('count-badge');
    const installModal = new bootstrap.Modal(document.getElementById('installModal'));

    function updateCount() { 
        const count = document.querySelectorAll('#sensorList input:checked').length;
        countBadge.innerText = count + " wybranych";
    }

    async function installCard() {
        const btn = document.getElementById('tab-install');
        const originalText = btn.innerHTML;
        btn.innerHTML = '<span class="spinner-border spinner-border-sm"></span> Instaluję...';
        
        try {
            const res = await fetch('api/install_card', { method: 'POST' });
            const data = await res.json();
            if(data.success) {
                alert("SUKCES! " + data.message + "\\n\\nOdśwież stronę (Ctrl+F5)!");
            } else {
                // FALLBACK: Kopiuj do schowka i pokaż ładne okno
                navigator.clipboard.writeText("/local/employee-card.js");
                installModal.show();
            }
        } catch (e) { 
            // Błąd sieci też traktujemy jak brak uprawnień
            navigator.clipboard.writeText("/local/employee-card.js");
            installModal.show();
        }
        btn.innerHTML = originalText;
    }

    function renderSensorList(filterText = "") {
        chkContainer.innerHTML = "";
        if (!ALL_SENSORS || ALL_SENSORS.length === 0) { chkContainer.innerHTML = '<div class="text-center text-danger p-3">Brak sensorów.</div>'; return; }
        ALL_SENSORS.forEach(s => {
            const searchStr = (s.name + s.id + s.main_label).toLowerCase();
            if (filterText && !searchStr.includes(filterText.toLowerCase())) return;
            const div = document.createElement('div');
            div.className = 'sensor-tile rounded p-2 d-flex align-items-center';
            let icon = "mdi-eye-circle-outline";
            if (s.main_label === "Temperatura") icon = "mdi-thermometer";
            else if (s.main_label === "Wilgotność") icon = "mdi-water-percent";
            else if (s.main_label === "Ciśnienie") icon = "mdi-gauge";
            else if (s.main_label === "Moc") icon = "mdi-lightning-bolt";
            else if (s.main_label === "Bateria") icon = "mdi-battery";
            div.innerHTML = `
                <div class="me-3 d-flex align-items-center justify-content-center bg-light rounded-circle" style="width:36px; height:36px;"><i class="mdi ${icon} fs-5 text-secondary"></i></div>
                <div style="flex: 1; min-width: 0;"><div class="tile-header text-truncate">${s.main_label}</div><div class="tile-sub text-truncate" title="${s.sub_label}">${s.sub_label}</div></div>
                <div class="tile-val">${s.state} <span style="font-size:0.7em">${s.unit}</span></div>
                <input class="form-check-input d-none" type="checkbox" value="${s.id}" id="chk_${s.id}">`;
            div.addEventListener('click', (e) => {
                const chk = div.querySelector('input');
                chk.checked = !chk.checked;
                if(chk.checked) div.classList.add('selected'); else div.classList.remove('selected');
                updateCount();
            });
            chkContainer.appendChild(div);
        });
    }
    document.getElementById('sensorSearch').addEventListener('input', (e) => renderSensorList(e.target.value));
    async function refreshMonitor() {
        if (!document.getElementById('tab-monitor').classList.contains('active')) return;
        try {
            const res = await fetch('api/monitor');
            const data = await res.json();
            const grid = document.getElementById('dashboard-grid');
            if(data.length === 0) { grid.innerHTML = '<p class="text-center mt-5">Brak danych.</p>'; return; }
            grid.innerHTML = data.map(emp => `
                <div class="col-md-6 col-xl-4"><div class="card h-100"><div class="card-body">
                    <div class="d-flex align-items-center mb-3"><div class="bg-light p-3 rounded-circle me-3"><i class="mdi mdi-account fs-3"></i></div>
                    <div><h5 class="mb-0 fw-bold">${emp.name}</h5><small class="${emp.status=='Pracuje'?'text-success': 'text-muted'}">● ${emp.status}</small></div>
                    <div class="ms-auto text-end"><div class="fs-4 fw-bold">${emp.work_time}</div><div class="small text-muted" style="font-size:0.7em">MIN</div></div></div>
                    <div class="row g-2">${emp.measurements.map(m => `<div class="col-6"><div class="p-2 border rounded bg-light text-center"><small class="text-muted d-block text-truncate">${m.label}</small><strong>${m.value} ${m.unit}</strong></div></div>`).join('')}</div>
                </div></div></div>`).join('');
        } catch(e){}
    }
    async function loadConfig() {
        const res = await fetch('api/employees');
        const data = await res.json();
        document.getElementById('configTable').innerHTML = data.map((emp, i) => `
            <tr><td><strong>${emp.name}</strong></td><td><span class="badge bg-secondary">${emp.sensors ? emp.sensors.length : 0}</span></td><td class="text-end"><button class="btn btn-sm btn-outline-danger" onclick="del(${i})">Usuń</button></td></tr>
        `).join('');
    }
    document.getElementById('addForm').onsubmit = async (e) => {
        e.preventDefault();
        const name = document.getElementById('empName').value;
        const selected = [];
        document.querySelectorAll('#sensorList input:checked').forEach(c => selected.push(c.value));
        if(selected.length === 0) return alert("Wybierz czujnik!");
        await fetch('api/employees', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: name, sensors: selected}) });
        document.getElementById('empName').value = '';
        renderSensorList(); loadConfig(); refreshMonitor(); alert('Zapisano!');
    };
    window.del = async (i) => { if(confirm("Usunąć?")) { await fetch('api/employees/'+i, { method: 'DELETE' }); loadConfig(); refreshMonitor(); } }
    renderSensorList(); loadConfig(); refreshMonitor(); setInterval(refreshMonitor, 3000);
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE, all_sensors=get_clean_sensors())

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
                elif unit == "V": label = "Napięcie"
                elif unit == "hPa": label = "Ciśnienie"
                elif unit == "%": label = "Wilgotność"
                meas.append({"label": label, "value": val, "unit": unit})
            except: pass
        res.append({"name": emp['name'], "status": status, "work_time": time, "measurements": meas})
    return jsonify(res)

@app.route('/api/install_card', methods=['POST'])
def api_install_card():
    success, msg = register_lovelace_resource()
    return jsonify({"success": success, "message": msg})