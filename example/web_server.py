import json
import os
import logging
from flask import Flask, request, jsonify, render_template_string
from employee_map import SENSOR_MAP

# Plik, w którym będziemy trzymać listę pracowników
DATA_FILE = "/data/employees.json"

app = Flask(__name__)
_LOGGER = logging.getLogger(__name__)

# Funkcje pomocnicze do zapisu/odczytu
def load_employees():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    except:
        return []

def save_employees(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- HTML TEMPLATE (Interfejs użytkownika) ---
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
    <title>Employee Manager</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css">
    <style>
        body { background-color: #f5f5f5; padding: 20px; }
        .card { margin-bottom: 20px; }
        .sensor-tag { margin-right: 5px; }
    </style>
</head>
<body>
<div class="container">
    <h1 class="mb-4">👥 Zarządzanie Pracownikami</h1>
    
    <div class="card shadow-sm">
        <div class="card-header bg-primary text-white">Dodaj / Edytuj Pracownika</div>
        <div class="card-body">
            <form id="addForm">
                <div class="mb-3">
                    <label class="form-label">Imię i Nazwisko</label>
                    <input type="text" class="form-control" id="empName" required placeholder="np. Jan Kowalski">
                </div>
                <div class="mb-3">
                    <label class="form-label">Przypisz Czujniki:</label>
                    <div id="sensorList" class="d-flex flex-wrap gap-2">
                        </div>
                </div>
                <button type="submit" class="btn btn-success">Zapisz Pracownika</button>
            </form>
        </div>
    </div>

    <div class="card shadow-sm">
        <div class="card-header">Lista Pracowników</div>
        <div class="card-body">
            <table class="table table-striped">
                <thead><tr><th>Imię</th><th>Przypisane Czujniki</th><th>Akcje</th></tr></thead>
                <tbody id="empTable"></tbody>
            </table>
        </div>
    </div>
</div>

<script>
    const SENSORS = {{ sensor_map | tojson }};
    
    // 1. Generowanie checkboxów
    const sensorContainer = document.getElementById('sensorList');
    for (const [name, data] of Object.entries(SENSORS)) {
        sensorContainer.innerHTML += `
            <div class="form-check border p-2 rounded bg-white">
                <input class="form-check-input" type="checkbox" value="${name}" id="chk_${name}">
                <label class="form-check-label" for="chk_${name}">${name}</label>
            </div>
        `;
    }

    // 2. Pobieranie i wyświetlanie listy
    async function loadTable() {
        const res = await fetch('api/employees');
        const employees = await res.json();
        const tbody = document.getElementById('empTable');
        tbody.innerHTML = '';
        
        employees.forEach((emp, index) => {
            const sensorsBadges = emp.sensors.map(s => `<span class="badge bg-info text-dark">${s}</span>`).join(' ');
            tbody.innerHTML += `
                <tr>
                    <td><strong>${emp.name}</strong></td>
                    <td>${sensorsBadges}</td>
                    <td><button class="btn btn-danger btn-sm" onclick="deleteEmp(${index})">Usuń</button></td>
                </tr>
            `;
        });
    }

    // 3. Zapisywanie
    document.getElementById('addForm').onsubmit = async (e) => {
        e.preventDefault();
        const name = document.getElementById('empName').value;
        
        // Zbieramy zaznaczone checkboxy
        const selectedSensors = [];
        document.querySelectorAll('#sensorList input:checked').forEach(chk => {
            selectedSensors.push(chk.value);
        });

        if (selectedSensors.length === 0) {
            alert("Wybierz przynajmniej jeden czujnik!");
            return;
        }

        await fetch('api/employees', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({name: name, sensors: selectedSensors})
        });
        
        document.getElementById('empName').value = '';
        document.querySelectorAll('#sensorList input').forEach(c => c.checked = false);
        loadTable();
    };

    // 4. Usuwanie
    window.deleteEmp = async (index) => {
        if(confirm("Na pewno usunąć?")) {
            await fetch('api/employees/' + index, { method: 'DELETE' });
            loadTable();
        }
    }

    loadTable();
</script>
</body>
</html>
"""

@app.route('/')
def index():
    # Przekazujemy mapę czujników do frontendu
    return render_template_string(HTML_PAGE, sensor_map=SENSOR_MAP)

# --- API ---

@app.route('/api/employees', methods=['GET'])
def get_employees():
    return jsonify(load_employees())

@app.route('/api/employees', methods=['POST'])
def add_employee():
    data = request.json
    employees = load_employees()
    
    # Prosta walidacja - usuwamy starego o tym imieniu i dodajemy nowego (Update/Insert)
    employees = [e for e in employees if e['name'] != data['name']]
    employees.append(data)
    
    save_employees(employees)
    return jsonify({"status": "ok"})

@app.route('/api/employees/<int:index>', methods=['DELETE'])
def delete_employee(index):
    employees = load_employees()
    if 0 <= index < len(employees):
        del employees[index]
        save_employees(employees)
    return jsonify({"status": "ok"})
