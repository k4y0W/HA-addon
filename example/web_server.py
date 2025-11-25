import json
import os
import logging
import requests
from flask import Flask, request, jsonify, render_template_string

DATA_FILE = "/data/employees.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
API_URL = "http://supervisor/core/api"
HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    "Content-Type": "application/json",
}

app = Flask(__name__)

# --- BACKEND ---
def load_employees():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def save_employees(data):
    with open(DATA_FILE, 'w') as f: json.dump(data, f, indent=4)

# Pobiera WSZYSTKIE sensory z Home Assistant
def get_all_sensors():
    sensors = []
    try:
        resp = requests.get(f"{API_URL}/states", headers=HEADERS)
        if resp.status_code == 200:
            all_states = resp.json()
            for entity in all_states:
                eid = entity['entity_id']
                # Filtrujemy: bierzemy tylko sensory i binary_sensory (np. ruch)
                if eid.startswith("sensor.") or eid.startswith("binary_sensor."):
                    # Pobieramy ludzką nazwę, a jak nie ma, to ID
                    name = entity.get("attributes", {}).get("friendly_name", eid)
                    unit = entity.get("attributes", {}).get("unit_of_measurement", "")
                    
                    sensors.append({
                        "id": eid,
                        "name": name,
                        "unit": unit,
                        "state": entity.get("state", "-")
                    })
            # Sortujemy alfabetycznie po ludzkiej nazwie
            sensors.sort(key=lambda x: x['name'])
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

# --- FRONTEND ---
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
        
        /* Styl kafelków czujników */
        .sensor-tile {
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid #dee2e6;
            background: white;
            font-size: 0.9rem;
        }
        .sensor-tile:hover { background-color: #e9ecef; transform: translateY(-1px); }
        /* Styl zaznaczonego kafelka */
        .sensor-tile.selected { 
            border-color: #0d6efd; 
            background-color: #e7f1ff; 
            color: #0d6efd; 
            font-weight: 600;
            box-shadow: 0 0 0 1px #0d6efd;
        }
        
        /* Scrollbox dla listy czujników (żeby nie zajmowała całej strony) */
        .sensor-list-container {
            max-height: 400px;
            overflow-y: auto;
            border: 1px solid #eee;
            padding: 10px;
            border-radius: 8px;
            background: #fff;
        }

        .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 6px; }
        .bg-working { background-color: #28a745; }
        .bg-idle { background-color: #ffc107; }
        .bg-absent { background-color: #dc3545; }
    </style>
</head>
<body>

<div class="container" style="max-width: 1000px;">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3 class="fw-bold text-primary"><i class="mdi mdi-account-supervisor-circle"></i> Employee Manager</h3>
        <ul class="nav nav-pills bg-white p-1 rounded shadow-sm">
            <li class="nav-item"><button class="nav-link active" id="tab-monitor" data-bs-toggle="pill" data-bs-target="#pills-monitor">Monitor</button></li>
            <li class="nav-item"><button class="nav-link" id="tab-config" data-bs-toggle="pill" data-bs-target="#pills-config">Konfiguracja</button></li>
        </ul>
    </div>

    <div class="tab-content">
        <div class="tab-pane fade show active" id="pills-monitor">
            <div class="row g-3" id="dashboard-grid"></div>
        </div>

        <div class="tab-pane fade" id="pills-config">
            <div class="row">
                <div class="col-lg-6">
                    <div class="card shadow-sm mb-4">
                        <div class="card-header bg-white fw-bold">Dodaj / Edytuj</div>
                        <div class="card-body">
                            <form id="addForm">
                                <div class="mb-3">
                                    <label class="form-label fw-bold">Imię Pracownika</label>
                                    <input type="text" class="form-control" id="empName" required placeholder="np. Antek">
                                </div>
                                
                                <div class="mb-3">
                                    <label class="form-label fw-bold">Przypisz Czujniki (Wybierz z listy)</label>
                                    <input type="text" class="form-control form-control-sm mb-2" id="sensorSearch" placeholder="🔍 Szukaj czujnika...">
                                    
                                    <div class="sensor-list-container">
                                        <div id="sensorList" class="d-flex flex-column gap-2"></div>
                                    </div>
                                    <div class="form-text">Zaznacz wszystkie czujniki (Moc, Temp, Ruch) należące do tej osoby.</div>
                                </div>

                                <button type="submit" class="btn btn-primary w-100">Zapisz Pracownika</button>
                            </form>
                        </div>
                    </div>
                </div>

                <div class="col-lg-6">
                    <div class="card shadow-sm">
                        <div class="card-header bg-white fw-bold">Lista Pracowników</div>
                        <div class="card-body p-0">
                            <table class="table table-hover mb-0 align-middle">
                                <thead class="table-light"><tr><th>Imię</th><th>Liczba czujników</th><th></th></tr></thead>
                                <tbody id="configTable"></tbody>
                            </table>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    // Lista WSZYSTKICH sensorów z HA przekazana przez Python
    const ALL_SENSORS = {{ all_sensors | tojson }};

    // 1. GENEROWANIE LISTY CZUJNIKÓW
    const chkContainer = document.getElementById('sensorList');
    
    function renderSensorList(filterText = "") {
        chkContainer.innerHTML = "";
        ALL_SENSORS.forEach(s => {
            // Filtrowanie po nazwie
            if (filterText && !s.name.toLowerCase().includes(filterText.toLowerCase()) && !s.id.includes(filterText)) return;

            const div = document.createElement('div');
            div.className = 'sensor-tile rounded p-2 d-flex align-items-center justify-content-between';
            
            // Ikona zależna od jednostki (prosta logika)
            let icon = "mdi-eye";
            if (s.unit === "W") icon = "mdi-lightning-bolt";
            else if (s.unit === "°C") icon = "mdi-thermometer";
            else if (s.unit === "%") icon = "mdi-water-percent";
            else if (s.unit === "hPa") icon = "mdi-gauge";

            div.innerHTML = `
                <div class="d-flex align-items-center overflow-hidden">
                    <input class="form-check-input me-2 flex-shrink-0" type="checkbox" value="${s.id}" id="chk_${s.id}">
                    <label class="form-check-label text-truncate" for="chk_${s.id}" title="${s.id}">
                        <i class="mdi ${icon} text-secondary me-1"></i> ${s.name}
                    </label>
                </div>
                <span class="badge bg-light text-dark border ms-2">${s.state} ${s.unit || ''}</span>
            `;
            
            // Klikanie w kafelek
            div.addEventListener('click', (e) => {
                if(e.target.tagName !== 'INPUT') {
                    const chk = div.querySelector('input');
                    chk.checked = !chk.checked;
                }
                const chk = div.querySelector('input');
                if(chk.checked) div.classList.add('selected'); else div.classList.remove('selected');
            });
            
            chkContainer.appendChild(div);
        });
    }

    // Wyszukiwarka
    document.getElementById('sensorSearch').addEventListener('input', (e) => renderSensorList(e.target.value));

    // --- LOGIKA MONITOR ---
    async function refreshMonitor() {
        if (!document.getElementById('tab-monitor').classList.contains('active')) return;
        try {
            const res = await fetch('api/monitor');
            const data = await res.json();
            const grid = document.getElementById('dashboard-grid');
            
            if(data.length === 0) { grid.innerHTML = '<p class="text-center mt-5">Brak danych.</p>'; return; }

            grid.innerHTML = data.map(emp => {
                let dot = 'bg-secondary';
                if(emp.status === 'Pracuje') dot = 'bg-working';
                else if(emp.status === 'Nieobecny') dot = 'bg-absent';
                else dot = 'bg-idle';

                let measHtml = emp.measurements.map(m => `
                    <div class="col-6"><div class="p-2 border rounded bg-light text-center h-100 d-flex flex-column justify-content-center">
                        <small class="text-muted d-block text-truncate" title="${m.label}">${m.label}</small>
                        <strong style="font-size:0.9rem">${m.value} ${m.unit}</strong>
                    </div></div>
                `).join('');

                return `
                <div class="col-md-6 col-xl-4">
                    <div class="card h-100">
                        <div class="card-body">
                            <div class="d-flex align-items-center mb-3">
                                <div class="bg-light p-3 rounded-circle me-3"><i class="mdi mdi-account fs-3"></i></div>
                                <div>
                                    <h5 class="mb-0 fw-bold">${emp.name}</h5>
                                    <small><span class="status-dot ${dot}"></span>${emp.status}</small>
                                </div>
                                <div class="ms-auto text-end">
                                    <div class="fs-4 fw-bold">${emp.work_time}</div>
                                    <div class="small text-muted" style="font-size:0.7em">MIN</div>
                                </div>
                            </div>
                            <div class="row g-2">${measHtml}</div>
                        </div>
                    </div>
                </div>`;
            }).join('');
        } catch(e){}
    }

    // --- KONFIGURACJA ---
    async function loadConfig() {
        const res = await fetch('api/employees');
        const data = await res.json();
        document.getElementById('configTable').innerHTML = data.map((emp, i) => `
            <tr>
                <td><strong>${emp.name}</strong></td>
                <td><span class="badge bg-primary">${emp.sensors ? emp.sensors.length : 0}</span></td>
                <td class="text-end"><button class="btn btn-sm btn-outline-danger" onclick="del(${i})">Usuń</button></td>
            </tr>
        `).join('');
    }

    document.getElementById('addForm').onsubmit = async (e) => {
        e.preventDefault();
        const name = document.getElementById('empName').value;
        const selected = [];
        // Pobieramy zaznaczone ID (entity_id)
        document.querySelectorAll('#sensorList input:checked').forEach(c => selected.push(c.value));

        if(selected.length === 0) return alert("Wybierz chociaż jeden czujnik!");

        await fetch('api/employees', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, sensors: selected}) # Zapisujemy listę ID
        });
        
        document.getElementById('empName').value = '';
        // Reset checkboxów
        renderSensorList(); 
        loadConfig();
        refreshMonitor();
        alert('Zapisano!');
    };

    window.del = async (i) => {
        if(confirm("Usunąć?")) {
            await fetch('api/employees/'+i, { method: 'DELETE' });
            loadConfig();
            refreshMonitor();
        }
    }

    renderSensorList();
    loadConfig();
    refreshMonitor();
    setInterval(refreshMonitor, 3000);
</script>
</body>
</html>
"""

@app.route('/')
def index():
    # Przekazujemy listę wszystkich sensorów do HTML
    return render_template_string(HTML_PAGE, all_sensors=get_all_sensors())

# API (bez zmian)
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
        # Teraz 'sensors' to lista ID (np. sensor.smart_plug_moc)
        for entity_id in emp.get('sensors', []):
            val = get_ha_state(entity_id)
            # Spróbujmy pobrać ładną nazwę z HA
            try:
                r = requests.get(f"{API_URL}/states/{entity_id}", headers=HEADERS)
                if r.status_code == 200:
                    data = r.json()
                    name = data['attributes'].get('friendly_name', entity_id)
                    unit = data['attributes'].get('unit_of_measurement', '')
                    meas.append({"label": name, "value": val, "unit": unit})
            except: pass
        
        res.append({"name": emp['name'], "status": status, "work_time": time, "measurements": meas})
    return jsonify(res)