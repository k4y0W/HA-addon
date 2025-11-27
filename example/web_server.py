import json
import os
import requests
import csv
import io
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string, Response

# ==========================================
# 1. TUTAJ WKLEJ SWÓJ DŁUGI TOKEN (W CUDZYSŁOWACH ""):
HARDCODED_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJjNmZiZjhkYjgzNzI0MWY0ODlkOWRhNjM1YWZkMmQ5MSIsImlhdCI6MTc2NDI1MTI5MywiZXhwIjoyMDc5NjExMjkzfQ.8ED4IyBltazDjbnzXsbyLwHg6zUF61EZ-aXUhR6BnEM" 
# ==========================================

DATA_FILE = "/data/employees.json"
GROUPS_FILE = "/data/groups.json"
OPTIONS_FILE = "/data/options.json"

# Konfiguracja API
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
USER_TOKEN_FROM_FILE = ""

try:
    with open(OPTIONS_FILE, 'r') as f:
        opts = json.load(f)
        USER_TOKEN_FROM_FILE = opts.get("ha_token", "")
except: pass

# Wybór tokena (Priorytet: Hardcoded > Plik > Supervisor)
if len(HARDCODED_TOKEN) > 50:
    TOKEN = HARDCODED_TOKEN
    API_URL = "http://homeassistant:8123/api"
elif len(USER_TOKEN_FROM_FILE) > 50:
    TOKEN = USER_TOKEN_FROM_FILE
    API_URL = "http://homeassistant:8123/api"
else:
    TOKEN = SUPERVISOR_TOKEN
    API_URL = "http://supervisor/core/api"

HEADERS = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json",
}

app = Flask(__name__)

SUFFIXES_TO_CLEAN = [
    "_status", "_czas_pracy", 
    "_temperatura", "_wilgotnosc", "_cisnienie", 
    "_moc", "_napiecie", "_natezenie", 
    "_bateria", "_pm25", "_jasnosc"
]

PRETTY_NAMES = {
    "temperature": "Temperatura", "humidity": "Wilgotność", "pressure": "Ciśnienie",
    "power": "Moc", "energy": "Energia", "voltage": "Napięcie", "current": "Natężenie",
    "battery": "Bateria", "signal_strength": "Sygnał", "pm25": "PM 2.5", "illuminance": "Jasność",
    "connectivity": "Połączenie"
}
BLOCKED_PREFIXES = ["sensor.backup_", "sensor.sun_", "sensor.date", "sensor.time", "sensor.zone", "sensor.automation", "sensor.script", "update.", "person.", "zone.", "sun.", "todo."]
BLOCKED_DEVICE_CLASSES = ["timestamp", "enum", "update", "date"]
GENERATED_SUFFIXES = SUFFIXES_TO_CLEAN

def load_json(file_path):
    if not os.path.exists(file_path):
        if file_path == GROUPS_FILE:
            default_groups = ["Domyślna"]
            save_json(GROUPS_FILE, default_groups)
            return default_groups
        return []
    try:
        with open(file_path, 'r') as f: return json.load(f)
    except: return []

def save_json(file_path, data):
    with open(file_path, 'w') as f: json.dump(data, f, indent=4)

def delete_ha_state(entity_id):
    try:
        requests.delete(f"{API_URL}/states/{entity_id}", headers=HEADERS)
    except: pass

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
                    if eid.endswith(suffix): is_virtual = True; break
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
    install_headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}
    try:
        url = f"{API_URL}/lovelace/resources"
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
        .group-filters { overflow-x: auto; white-space: nowrap; padding-bottom: 10px; }
        .group-btn { border-radius: 20px; padding: 5px 15px; border: 1px solid #dee2e6; background: white; margin-right: 5px; color: #555; transition:0.2s; cursor: pointer; }
        .group-btn:hover { background: #e9ecef; }
        .group-btn.active { background: #0d6efd; color: white; border-color: #0d6efd; }
    </style>
</head>
<body>

<div class="container" style="max-width: 1000px;">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3 class="fw-bold text-primary"><i class="mdi mdi-account-group"></i> Employee Manager</h3>
        <ul class="nav nav-pills bg-white p-1 rounded shadow-sm">
            <li class="nav-item"><button class="nav-link active" id="tab-monitor" data-bs-toggle="pill" data-bs-target="#pills-monitor">Monitor</button></li>
            <li class="nav-item"><button class="nav-link" id="tab-config" data-bs-toggle="pill" data-bs-target="#pills-config">Konfiguracja</button></li>
            <li class="nav-item"><button class="nav-link text-success fw-bold" id="tab-install" onclick="installCard()"><i class="mdi mdi-download"></i> Instaluj Kartę</button></li>
        </ul>
    </div>

    <div class="tab-content">
        <div class="tab-pane fade show active" id="pills-monitor">
            <div class="d-flex justify-content-between mb-3">
                <div class="group-filters d-flex" id="monitorFilters"></div>
                <a href="api/export_csv" target="_blank" class="btn btn-outline-dark btn-sm" style="white-space:nowrap"><i class="mdi mdi-file-excel"></i> CSV</a>
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
                                <div class="mb-3">
                                    <label class="form-label fw-bold">Imię i Nazwisko</label>
                                    <input type="text" class="form-control" id="empName" required placeholder="np. Jan Kowalski">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label fw-bold">Grupa (Dział)</label>
                                    <select class="form-select" id="empGroup">
                                        <option value="Domyślna">Domyślna</option>
                                    </select>
                                </div>
                                <div class="mb-3">
                                    <label class="form-label fw-bold d-flex justify-content-between">
                                        <span>Przypisz Czujniki</span>
                                        <span class="badge bg-light text-dark fw-normal border" id="count-badge">0 wybranych</span>
                                    </label>
                                    <input type="text" class="form-control form-control-sm mb-2" id="sensorSearch" placeholder="🔍 Filtruj...">
                                    
                                    <div class="sensor-list-container border rounded p-2 bg-light" style="max-height: 400px; overflow-y: auto;">
                                        <div id="sensorList" class="d-flex flex-column gap-2">
                                            <div class="text-center text-muted p-3">Ładowanie...</div>
                                        </div>
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
                    
                    <div class="card shadow-sm mt-3">
                        <div class="card-header bg-white fw-bold">Grupy</div>
                        <div class="card-body">
                            <form id="groupForm" class="mb-3">
                                <div class="input-group">
                                    <input type="text" class="form-control" id="newGroup" placeholder="Nowa grupa..." required>
                                    <button class="btn btn-success">Dodaj</button>
                                </div>
                            </form>
                            <ul class="list-group" id="groupList"></ul>
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
        <h5 class="modal-title">Instalacja Karty Lovelace</h5>
        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
      </div>
      <div class="modal-body">
        <p>Aby użyć karty na pulpicie:</p>
        <ol>
            <li>Skopiuj link poniżej.</li>
            <li>Kliknij <b>Otwórz Ustawienia</b>.</li>
            <li>Dodaj zasób, wklej link i wybierz <b>Moduł JavaScript</b>.</li>
        </ol>
        <div class="input-group mb-3">
            <input type="text" class="form-control bg-light" value="/local/employee-card.js" id="linkInput" readonly>
            <button class="btn btn-outline-primary" id="btn-copy" onclick="copyLink()">Kopiuj</button>
        </div>
        <a href="/config/lovelace/resources" target="_blank" class="btn btn-success w-100">Otwórz Ustawienia</a>
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
    
    let currentFilter = 'Wszyscy';
    let allEmployeesData = [];
    let currentGroups = [];

    function updateCount() { 
        const count = document.querySelectorAll('#sensorList input:checked').length;
        countBadge.innerText = count + " wybranych";
    }

    function copyLink() {
        const copyText = document.getElementById("linkInput");
        const btn = document.getElementById("btn-copy");
        copyText.select();
        copyText.setSelectionRange(0, 99999);
        try {
            document.execCommand('copy'); 
            const originalHtml = btn.innerHTML;
            btn.innerHTML = 'Skopiowano!';
            btn.classList.replace('btn-outline-primary', 'btn-success');
            setTimeout(() => {
                btn.innerHTML = originalHtml;
                btn.classList.replace('btn-success', 'btn-outline-primary');
            }, 2000);
        } catch (err) {}
    }

    async function installCard() {
        const btn = document.getElementById('tab-install');
        const originalText = btn.innerHTML; btn.innerHTML = '⏳ ...';
        try {
            const res = await fetch('api/install_card', { method: 'POST' });
            const data = await res.json();
            if(data.success) alert("SUKCES! " + data.message + "\\n\\nOdśwież stronę (Ctrl+F5)!");
            else installModal.show();
        } catch (e) { installModal.show(); }
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
                <div class="me-3 d-flex align-items-center justify-content-center bg-light rounded-circle" style="width:36px; height:36px;">
                    <i class="mdi ${icon} fs-5 text-secondary"></i>
                </div>
                <div style="flex: 1; min-width: 0;">
                    <div class="tile-header text-truncate">${s.main_label}</div>
                    <div class="tile-sub text-truncate" title="${s.sub_label}">${s.sub_label}</div>
                </div>
                <div class="tile-val">${s.state} <span style="font-size:0.7em">${s.unit}</span></div>
                <input class="form-check-input d-none" type="checkbox" value="${s.id}" id="chk_${s.id}">
            `;
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

    async function loadGroups() {
        const res = await fetch('api/groups');
        currentGroups = await res.json();
        
        document.getElementById('groupList').innerHTML = currentGroups.map(g => `<li class="list-group-item d-flex justify-content-between">${g} <button class="btn btn-sm btn-outline-danger" onclick="delGroup('${g}')">X</button></li>`).join('');
        
        document.getElementById('empGroup').innerHTML = currentGroups.map(g => `<option value="${g}">${g}</option>`).join('');
        
        renderFilterBar();
    }

    function renderFilterBar() {
        const filters = document.getElementById('monitorFilters');
        let html = `<button class="group-btn ${currentFilter==='Wszyscy'?'active':''}" onclick="filterMonitor('Wszyscy')">Wszyscy</button>`;
        currentGroups.forEach(g => {
            if(g !== 'Domyślna') html += `<button class="group-btn ${currentFilter===g?'active':''}" onclick="filterMonitor('${g}')">${g}</button>`;
        });
        filters.innerHTML = html;
    }
    
    document.getElementById('groupForm').onsubmit = async (e) => {
        e.preventDefault();
        await fetch('api/groups', { method:'POST', headers:{'Content-Type':'application/json'}, body:JSON.stringify({name: document.getElementById('newGroup').value}) });
        document.getElementById('newGroup').value=''; loadGroups();
    };
    
    window.delGroup = async (n) => { 
        if(n === 'Domyślna') return alert("Nie można usunąć grupy Domyślna!");
        if(confirm("Usunąć grupę?")) { await fetch('api/groups/'+n, {method:'DELETE'}); loadGroups(); loadConfig(); refreshMonitorData(); }
    };

    function filterMonitor(group) {
        currentFilter = group;
        renderFilterBar();
        renderGrid();
    }

    function renderGrid() {
        const grid = document.getElementById('dashboard-grid');
        const filtered = currentFilter === 'Wszyscy' ? allEmployeesData : allEmployeesData.filter(e => e.group === currentFilter);
        
        if(filtered.length === 0) { grid.innerHTML = '<p class="text-center mt-5 text-muted">Brak pracowników w tej grupie.</p>'; return; }
        
        grid.innerHTML = filtered.map(emp => `
            <div class="col-md-6 col-xl-4">
                <div class="card h-100">
                    <div class="card-body">
                        <div class="d-flex align-items-center mb-3">
                            <div class="bg-light p-3 rounded-circle me-3"><i class="mdi mdi-account fs-3"></i></div>
                            <div>
                                <h5 class="mb-0 fw-bold">${emp.name}</h5>
                                <small class="${emp.status=='Pracuje'?'text-success': 'text-muted'}">● ${emp.status}</small>
                                <span class="badge bg-light text-dark border ms-2">${emp.group || 'Domyślna'}</span>
                            </div>
                            <div class="ms-auto text-end"><div class="fs-4 fw-bold">${emp.work_time}</div><div class="small text-muted" style="font-size:0.7em">MIN</div></div>
                        </div>
                        <div class="row g-2">${emp.measurements.map(m => 
                            `<div class="col-6"><div class="p-2 border rounded bg-light text-center"><small class="text-muted d-block text-truncate">${m.label}</small><strong>${m.value} ${m.unit}</strong></div></div>`
                        ).join('')}</div>
                    </div>
                </div>
            </div>`).join('');
    }

    async function refreshMonitorData() {
        if (!document.getElementById('tab-monitor').classList.contains('active')) return;
        const res = await fetch('api/monitor');
        allEmployeesData = await res.json();
        renderGrid();
    }

    async function loadConfig() {
        const res = await fetch('api/employees');
        const data = await res.json();
        document.getElementById('configTable').innerHTML = data.map((emp, i) => `
            <tr><td><strong>${emp.name}</strong><br><span class="badge bg-secondary">${emp.group || 'Domyślna'}</span></td><td class="text-end"><button class="btn btn-sm btn-outline-danger" onclick="del(${i})">Usuń</button></td></tr>
        `).join('');
    }

    document.getElementById('addForm').onsubmit = async (e) => {
        e.preventDefault();
        const name = document.getElementById('empName').value;
        const group = document.getElementById('empGroup').value;
        const selected = [];
        document.querySelectorAll('#sensorList input:checked').forEach(c => selected.push(c.value));
        
        // --- BLOKADA PUSTYCH SENSORÓW ---
        if(selected.length === 0) {
            alert("Błąd: Musisz wybrać przynajmniej jeden czujnik!");
            return;
        }

        await fetch('api/employees', { method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({name: name, group: group, sensors: selected}) });
        document.getElementById('empName').value = '';
        renderSensorList(); loadConfig(); refreshMonitorData(); alert('Zapisano!');
    };

    window.del = async (i) => { if(confirm("Usunąć?")) { await fetch('api/employees/'+i, { method: 'DELETE' }); loadConfig(); refreshMonitorData(); } }

    renderSensorList(); loadGroups(); loadConfig(); refreshMonitorData(); setInterval(refreshMonitorData, 3000);
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE, all_sensors=get_clean_sensors())

@app.route('/api/groups', methods=['GET', 'POST'])
def handle_groups():
    grps = load_json(GROUPS_FILE)
    if not grps: grps = ["Domyślna"]
    if request.method == 'POST':
        name = request.json.get('name')
        if name and name not in grps: grps.append(name)
        save_json(GROUPS_FILE, grps)
    return jsonify(grps)

@app.route('/api/groups/<name>', methods=['DELETE'])
def del_group(name):
    if name == "Domyślna": return jsonify({"error": "Nie można usunąć"}), 400
    grps = load_json(GROUPS_FILE)
    if name in grps: grps.remove(name)
    save_json(GROUPS_FILE, grps)
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
    if 0 <= i < len(emps):
        to_delete = emps[i]
        safe_name = to_delete['name'].lower().replace(" ", "_")
        
        delete_ha_state(f"sensor.{safe_name}_status")
        delete_ha_state(f"sensor.{safe_name}_czas_pracy")
        for suffix in SUFFIXES_TO_CLEAN:
            delete_ha_state(f"sensor.{safe_name}{suffix}")
            
        del emps[i]
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
                meas.append({"label": label, "value": val, "unit": unit})
            except: pass
        res.append({"name": emp['name'], "group": emp.get('group', 'Domyślna'), "status": status, "work_time": time, "measurements": meas})
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

@app.route('/api/install_card', methods=['POST'])
def api_install_card():
    success, msg = register_lovelace_resource()
    return jsonify({"success": success, "message": msg})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)