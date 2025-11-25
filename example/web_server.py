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
            # Zaokrąglanie liczb
            try: return str(round(float(state), 1))
            except: return state
    except: pass
    return "-"

# --- FRONTEND (HTML/JS/CSS) ---
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
        body { background-color: #f0f2f5; font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; }
        .card-employee { transition: transform 0.2s; border: none; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }
        .card-employee:hover { transform: translateY(-5px); box-shadow: 0 8px 15px rgba(0,0,0,0.1); }
        .status-indicator { width: 15px; height: 15px; border-radius: 50%; display: inline-block; margin-right: 8px; }
        .status-working { background-color: #4caf50; box-shadow: 0 0 8px #4caf50; }
        .status-idle { background-color: #ffc107; }
        .status-absent { background-color: #f44336; }
        .nav-pills .nav-link.active { background-color: #039be5; }
        .sensor-value { font-size: 1.2rem; font-weight: bold; color: #333; }
        .sensor-label { font-size: 0.85rem; color: #777; }
    </style>
</head>
<body>

<div class="container py-4">
    <div class="d-flex justify-content-between align-items-center mb-4">
        <h2 class="fw-bold text-dark"><i class="mdi mdi-office-building"></i> Panel Pracowników</h2>
        <ul class="nav nav-pills" id="pills-tab" role="tablist">
            <li class="nav-item" role="presentation">
                <button class="nav-link active" id="pills-monitor-tab" data-bs-toggle="pill" data-bs-target="#pills-monitor" type="button">
                    <i class="mdi mdi-view-dashboard"></i> Monitor
                </button>
            </li>
            <li class="nav-item" role="presentation">
                <button class="nav-link" id="pills-config-tab" data-bs-toggle="pill" data-bs-target="#pills-config" type="button">
                    <i class="mdi mdi-cog"></i> Konfiguracja
                </button>
            </li>
        </ul>
    </div>

    <div class="tab-content" id="pills-tabContent">
        
        <div class="tab-pane fade show active" id="pills-monitor">
            <div class="row g-4" id="dashboard-grid">
                <div class="text-center py-5"><div class="spinner-border text-primary"></div><p>Ładowanie danych...</p></div>
            </div>
        </div>

        <div class="tab-pane fade" id="pills-config">
            <div class="row">
                <div class="col-md-4">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header bg-white fw-bold">Dodaj Osobę</div>
                        <div class="card-body">
                            <form id="addForm">
                                <div class="mb-3">
                                    <label class="form-label">Imię i Nazwisko</label>
                                    <input type="text" class="form-control" id="empName" required placeholder="np. Anna Nowak">
                                </div>
                                <div class="mb-3">
                                    <label class="form-label">Wybierz Pomiary:</label>
                                    <div id="sensorCheckboxes" class="d-flex flex-column gap-2"></div>
                                </div>
                                <button type="submit" class="btn btn-primary w-100">Zapisz</button>
                            </form>
                        </div>
                    </div>
                </div>
                <div class="col-md-8">
                    <div class="card border-0 shadow-sm">
                        <div class="card-header bg-white fw-bold">Lista Pracowników</div>
                        <div class="card-body p-0">
                            <table class="table table-hover mb-0 align-middle">
                                <thead class="table-light"><tr><th>Pracownik</th><th>Przypisane Czujniki</th><th class="text-end">Akcja</th></tr></thead>
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
    const SENSORS_MAP = {{ sensor_map | tojson }};

    // --- GENEROWANIE CHECKBOXÓW ---
    const chkContainer = document.getElementById('sensorCheckboxes');
    for (const [key, val] of Object.entries(SENSORS_MAP)) {
        chkContainer.innerHTML += `
            <div class="form-check">
                <input class="form-check-input" type="checkbox" value="${key}" id="chk_${key}">
                <label class="form-check-label" for="chk_${key}">
                    <i class="mdi ${val.icon}"></i> ${key}
                </label>
            </div>`;
    }

    // --- LOGIKA DASHBOARDU (MONITOR) ---
    async function refreshMonitor() {
        // Jeśli user nie jest na zakładce monitora, nie odświeżaj (oszczędzaj zasoby)
        if (!document.getElementById('pills-monitor-tab').classList.contains('active')) return;

        try {
            const res = await fetch('api/monitor');
            const data = await res.json();
            const grid = document.getElementById('dashboard-grid');
            
            if (data.length === 0) {
                grid.innerHTML = '<div class="col-12 text-center text-muted"><h3>Brak pracowników</h3><p>Przejdź do zakładki Konfiguracja aby dodać pierwszą osobę.</p></div>';
                return;
            }

            grid.innerHTML = '';
            data.forEach(emp => {
                // Wybór koloru statusu
                let statusDot = 'status-idle';
                let statusTextClass = 'text-warning';
                if (emp.status === 'Pracuje') { statusDot = 'status-working'; statusTextClass = 'text-success'; }
                else if (emp.status === 'Nieobecny') { statusDot = 'status-absent'; statusTextClass = 'text-danger'; }

                // Generowanie sekcji pomiarów
                let measurementsHtml = '';
                emp.measurements.forEach(m => {
                    measurementsHtml += `
                        <div class="col-6 mb-2">
                            <div class="bg-light p-2 rounded text-center">
                                <div class="sensor-label">${m.label}</div>
                                <div class="sensor-value">${m.value}<small class="text-muted" style="font-size:0.6em">${m.unit}</small></div>
                            </div>
                        </div>
                    `;
                });

                grid.innerHTML += `
                    <div class="col-md-6 col-xl-4">
                        <div class="card card-employee h-100">
                            <div class="card-body">
                                <div class="d-flex align-items-center mb-3">
                                    <div class="bg-primary bg-opacity-10 p-3 rounded-circle text-primary me-3">
                                        <i class="mdi mdi-account-circle fs-2"></i>
                                    </div>
                                    <div>
                                        <h5 class="card-title mb-0 fw-bold">${emp.name}</h5>
                                        <small class="${statusTextClass} fw-bold">
                                            <span class="status-indicator ${statusDot}"></span>${emp.status}
                                        </small>
                                    </div>
                                </div>
                                <hr class="text-muted opacity-25">
                                <div class="row">
                                    ${measurementsHtml}
                                </div>
                            </div>
                        </div>
                    </div>
                `;
            });
        } catch (e) { console.error(e); }
    }

    // --- LOGIKA KONFIGURACJI ---
    async function loadConfig() {
        const res = await fetch('api/employees');
        const data = await res.json();
        const tbody = document.getElementById('configTable');
        tbody.innerHTML = '';
        data.forEach((emp, idx) => {
            tbody.innerHTML += `
                <tr>
                    <td class="fw-bold">${emp.name}</td>
                    <td>${emp.sensors.map(s => `<span class="badge bg-secondary me-1">${s}</span>`).join('')}</td>
                    <td class="text-end"><button class="btn btn-sm btn-outline-danger" onclick="deleteEmp(${idx})"><i class="mdi mdi-delete"></i></button></td>
                </tr>
            `;
        });
    }

    document.getElementById('addForm').onsubmit = async (e) => {
        e.preventDefault();
        const name = document.getElementById('empName').value;
        const selected = [];
        document.querySelectorAll('#sensorCheckboxes input:checked').forEach(c => selected.push(c.value));
        
        if(selected.length === 0) return alert("Wybierz co najmniej jeden czujnik!");

        await fetch('api/employees', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, sensors: selected})
        });
        
        document.getElementById('empName').value = '';
        document.querySelectorAll('#sensorCheckboxes input').forEach(c => c.checked = false);
        loadConfig();
        refreshMonitor();
    };

    window.deleteEmp = async (idx) => {
        if(confirm("Usunąć pracownika?")) {
            await fetch('api/employees/' + idx, { method: 'DELETE' });
            loadConfig();
            refreshMonitor();
        }
    };

    // Inicjalizacja
    loadConfig();
    refreshMonitor();
    setInterval(refreshMonitor, 3000); // Odświeżanie live co 3 sekundy

</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE, sensor_map=SENSOR_MAP)

# --- API ---
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
        # Pobieranie danych na żywo z HA
        measurements = []
        for s_name in emp.get('sensors', []):
            s_def = SENSOR_MAP.get(s_name)
            if s_def:
                val = get_ha_state(f"sensor.{safe_name}_{s_name.lower()}")
                measurements.append({"label": s_name, "value": val, "unit": s_def['unit']})
        
        # Status (jeśli masz logikę statusu w pythonie, ona też tworzy sensory)
        # Tutaj dla uproszczenia zakładam, że logika Pythona tworzy sensor.{name}_status
        # Jeśli nie, możesz tu wstawić "N/A"
        status = get_ha_state(f"sensor.{safe_name}_status") or "Nieznany"

        result.append({
            "name": emp['name'],
            "status": status,
            "measurements": measurements
        })
    return jsonify(result)