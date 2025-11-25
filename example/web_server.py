import json
import os
import logging
import requests
from flask import Flask, request, jsonify, render_template_string
from employee_map import SENSOR_MAP

DATA_FILE = "/data/employees.json"
SUPERVISOR_TOKEN = os.environ.get("SUPERVISOR_TOKEN")
API_URL = "http://supervisor/core/api"
HEADERS = {
    "Authorization": f"Bearer {SUPERVISOR_TOKEN}",
    "Content-Type": "application/json",
}

app = Flask(__name__)
_LOGGER = logging.getLogger(__name__)

# --- BACKEND ---
def load_employees():
    if not os.path.exists(DATA_FILE): return []
    try:
        with open(DATA_FILE, 'r') as f: return json.load(f)
    except: return []

def save_employees(data):
    with open(DATA_FILE, 'w') as f: json.dump(data, f, indent=4)

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
        body { background-color: #f8f9fa; font-family: system-ui, -apple-system, sans-serif; padding: 20px; }
        
        /* Styl kafelków czujników w formularzu */
        .sensor-tile {
            cursor: pointer;
            transition: all 0.2s;
            border: 1px solid #dee2e6;
            background: white;
        }
        .sensor-tile:hover { background-color: #e9ecef; transform: translateY(-2px); }
        .sensor-tile input:checked + label { color: #0d6efd; font-weight: bold; }
        /* Podświetlenie kafelka gdy zaznaczony - wymaga JS lub CSS :has (nowsze przeglądarki) */
        .sensor-tile.selected { border-color: #0d6efd; background-color: #e7f1ff; }

        .card { border: none; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border-radius: 12px; margin-bottom: 20px; }
        .card-header { background: white; border-bottom: 1px solid #f0f0f0; font-weight: 600; padding: 15px; border-radius: 12px 12px 0 0 !important; }
        
        /* Styl monitora */
        .status-dot { height: 10px; width: 10px; border-radius: 50%; display: inline-block; margin-right: 6px; }
        .bg-working { background-color: #28a745; box-shadow: 0 0 5px #28a745; }
        .bg-idle { background-color: #ffc107; }
        .bg-absent { background-color: #dc3545; }
    </style>
</head>
<body>

<div class="container" style="max-width: 900px;">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h3 class="fw-bold m-0"><i class="mdi mdi-account-supervisor-circle text-primary"></i> Employee Manager</h3>
        <ul class="nav nav-pills bg-white p-1 rounded shadow-sm" id="pills-tab" role="tablist">
            <li class="nav-item">
                <button class="nav-link active" id="pills-monitor-tab" data-bs-toggle="pill" data-bs-target="#pills-monitor">Monitor</button>
            </li>
            <li class="nav-item">
                <button class="nav-link" id="pills-config-tab" data-bs-toggle="pill" data-bs-target="#pills-config">Konfiguracja</button>
            </li>
        </ul>
    </div>

    <div class="tab-content">
        
        <div class="tab-pane fade show active" id="pills-monitor">
            <div class="row g-3" id="dashboard-grid">
                <div class="text-center py-5 text-muted">Ładowanie danych...</div>
            </div>
        </div>

        <div class="tab-pane fade" id="pills-config">
            
            <div class="card mb-4">
                <div class="card-header text-primary">Dodaj / Edytuj Pracownika</div>
                <div class="card-body">
                    <form id="addForm">
                        <div class="mb-3">
                            <label class="form-label small text-muted text-uppercase fw-bold">Imię i Nazwisko</label>
                            <input type="text" class="form-control form-control-lg" id="empName" required placeholder="np. Jan Kowalski">
                        </div>
                        
                        <div class="mb-3">
                            <label class="form-label small text-muted text-uppercase fw-bold">Przypisz Czujniki</label>
                            <div id="sensorList" class="d-flex flex-wrap gap-2">
                                </div>
                        </div>
                        <button type="submit" class="btn btn-primary px-4">Zapisz Pracownika</button>
                    </form>
                </div>
            </div>

            <div class="card">
                <div class="card-header">Lista Pracowników</div>
                <div class="card-body p-0">
                    <div class="table-responsive">
                        <table class="table table-hover mb-0 align-middle">
                            <thead class="table-light"><tr><th>Pracownik</th><th>Czujniki</th><th class="text-end">Opcje</th></tr></thead>
                            <tbody id="configTable"></tbody>
                        </table>
                    </div>
                </div>
            </div>
        </div>
    </div>
</div>

<script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
<script>
    const SENSORS_MAP = {{ sensor_map | tojson }};

    // GENEROWANIE ŁADNYCH KAFELKÓW (CHECKBOXÓW)
    const chkContainer = document.getElementById('sensorList');
    for (const [key, val] of Object.entries(SENSORS_MAP)) {
        // Tworzymy unikalny element kafelka
        const wrapper = document.createElement('div');
        wrapper.className = 'sensor-tile rounded p-2 d-flex align-items-center';
        wrapper.style.minWidth = '140px';
        
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.value = key;
        input.id = 'chk_' + key;
        input.className = 'form-check-input me-2 mt-0';
        input.style.cursor = 'pointer';
        
        // Efekt wizualny przy kliknięciu
        input.addEventListener('change', function() {
            if(this.checked) wrapper.classList.add('selected', 'border-primary');
            else wrapper.classList.remove('selected', 'border-primary');
        });

        const label = document.createElement('label');
        label.htmlFor = 'chk_' + key;
        label.className = 'form-check-label w-100';
        label.style.cursor = 'pointer';
        label.innerHTML = `<i class="mdi ${val.icon} me-1 text-secondary"></i> ${key}`;

        wrapper.appendChild(input);
        wrapper.appendChild(label);
        chkContainer.appendChild(wrapper);
    }

    // --- API & LOGIKA ---
    async function refreshMonitor() {
        if (!document.getElementById('pills-monitor-tab').classList.contains('active')) return;
        try {
            const res = await fetch('api/monitor');
            const data = await res.json();
            const grid = document.getElementById('dashboard-grid');
            
            if (data.length === 0) {
                grid.innerHTML = '<div class="col-12 text-center p-4 text-muted">Brak pracowników. Dodaj ich w konfiguracji.</div>';
                return;
            }
            grid.innerHTML = '';
            data.forEach(emp => {
                let statusDot = 'bg-secondary';
                if (emp.status === 'Pracuje') statusDot = 'bg-working';
                else if (emp.status === 'Obecny (Idle)') statusDot = 'bg-idle';
                else if (emp.status === 'Nieobecny') statusDot = 'bg-absent';

                let sensorsHtml = '';
                emp.measurements.forEach(m => {
                    sensorsHtml += `
                        <div class="col-6 mb-2">
                            <div class="p-2 bg-white border rounded text-center">
                                <div class="small text-muted">${m.label}</div>
                                <div class="fw-bold">${m.value} <span style="font-size:0.7em">${m.unit}</span></div>
                            </div>
                        </div>`;
                });

                grid.innerHTML += `
                    <div class="col-md-6 col-xl-4">
                        <div class="card h-100">
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="bg-light rounded-circle p-3 me-3"><i class="mdi mdi-account fs-4 text-secondary"></i></div>
                                    <div>
                                        <h5 class="card-title mb-0">${emp.name}</h5>
                                        <small><span class="status-dot ${statusDot}"></span>${emp.status}</small>
                                    </div>
                                </div>
                                <div class="row g-2 bg-light p-2 rounded mb-0">
                                    ${sensorsHtml}
                                </div>
                            </div>
                        </div>
                    </div>`;
            });
        } catch(e) {}
    }

    async function loadConfig() {
        const res = await fetch('api/employees');
        const data = await res.json();
        const tbody = document.getElementById('configTable');
        tbody.innerHTML = '';
        data.forEach((emp, idx) => {
            tbody.innerHTML += `
                <tr>
                    <td class="fw-bold">${emp.name}</td>
                    <td>${emp.sensors.map(s => `<span class="badge bg-light text-dark border me-1">${s}</span>`).join('')}</td>
                    <td class="text-end"><button class="btn btn-sm btn-light text-danger" onclick="deleteEmp(${idx})"><i class="mdi mdi-trash-can"></i></button></td>
                </tr>`;
        });
    }

    document.getElementById('addForm').onsubmit = async (e) => {
        e.preventDefault();
        const name = document.getElementById('empName').value;
        const selected = [];
        document.querySelectorAll('#sensorList input:checked').forEach(c => selected.push(c.value));
        
        if(selected.length === 0) return alert("Wybierz czujnik!");

        await fetch('api/employees', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, sensors: selected})
        });
        
        document.getElementById('empName').value = '';
        document.querySelectorAll('#sensorList input').forEach(c => { c.checked = false; c.parentElement.classList.remove('selected', 'border-primary'); });
        loadConfig();
        refreshMonitor();
        alert("Zapisano!");
    };

    window.deleteEmp = async (idx) => {
        if(confirm("Usunąć?")) {
            await fetch('api/employees/' + idx, { method: 'DELETE' });
            loadConfig();
            refreshMonitor();
        }
    };

    loadConfig();
    refreshMonitor();
    setInterval(refreshMonitor, 3000);
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE, sensor_map=SENSOR_MAP)

# API (To samo co wcześniej)
@app.route('/api/employees', methods=['GET'])
def api_get_emp(): return jsonify(load_employees())

@app.route('/api/employees', methods=['POST'])
def api_add_emp():
    data = request.json
    emps = load_employees()
    emps = [e for e in emps if e['name'] != data['name']]
    emps.append(data)
    save_employees(emps)
    return jsonify({"status":"ok"})

@app.route('/api/employees/<int:idx>', methods=['DELETE'])
def api_del_emp(idx):
    emps = load_employees()
    if 0 <= idx < len(emps): del emps[idx]
    save_employees(emps)
    return jsonify({"status":"ok"})

@app.route('/api/monitor', methods=['GET'])
def api_monitor():
    emps = load_employees()
    result = []
    for emp in emps:
        safe_name = emp['name'].lower().replace(" ", "_")
        status = get_ha_state(f"sensor.{safe_name}_status") or "Nieznany"
        work_time = get_ha_state(f"sensor.{safe_name}_czas_pracy")
        measurements = []
        for s_name in emp.get('sensors', []):
            s_def = SENSOR_MAP.get(s_name)
            if s_def:
                val = get_ha_state(f"sensor.{safe_name}_{s_name.lower()}")
                measurements.append({"label": s_name, "value": val, "unit": s_def['unit']})
        
        result.append({"name": emp['name'], "status": status, "measurements": measurements})
    return jsonify(result)