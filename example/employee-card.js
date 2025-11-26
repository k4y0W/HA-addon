const KNOWN_SENSOR_TYPES = [
  { suffix: 'temperatura', icon: 'mdi:thermometer', unit: '°C' },
  { suffix: 'wilgotnosc', icon: 'mdi:water-percent', unit: '%' },
  { suffix: 'cisnienie', icon: 'mdi:gauge', unit: 'hPa' },
  { suffix: 'moc', icon: 'mdi:lightning-bolt', unit: 'W' },
  { suffix: 'napiecie', icon: 'mdi:sine-wave', unit: 'V' },
  { suffix: 'natezenie', icon: 'mdi:current-ac', unit: 'A' },
  { suffix: 'bateria', icon: 'mdi:battery', unit: '%' },
  { suffix: 'pm25', icon: 'mdi:blur', unit: 'μg/m³' },
  { suffix: 'pm25_density', icon: 'mdi:blur', unit: 'μg/m³' }
];

const SHARED_STYLES = `
  .emp-card { 
    background: var(--ha-card-background, white); 
    border-radius: 12px; 
    box-shadow: var(--ha-card-box-shadow, 0 2px 5px rgba(0,0,0,0.15)); 
    padding: 16px; 
    border: 1px solid var(--divider-color, #ddd);
    margin-bottom: 12px;
    transition: transform 0.1s;
  }
  .emp-card:hover { transform: scale(1.01); border-color: #bbb; }
  
  .header { display: flex; align-items: center; width: 100%; margin-bottom: 14px; }
  
  .icon-box { 
    width: 48px; height: 48px; 
    border-radius: 50%; 
    display: flex; align-items: center; justify-content: center; 
    margin-right: 16px; 
    background: #eee; color: #444;
    font-weight: bold;
  }
  
  .is-working { background: #E8F5E9; color: #1B5E20; border: 2px solid #4CAF50; }
  .is-idle { background: #FFFDE7; color: #E65100; border: 2px solid #FFC107; }
  .is-absent { background: #FFEBEE; color: #B71C1C; border: 2px solid #EF5350; }

  .info { flex: 1; }
  .emp-name { font-weight: 800; font-size: 1.3rem; color: var(--primary-text-color); line-height: 1.2; }
  .emp-status { font-size: 1rem; color: var(--secondary-text-color); font-weight: 600; margin-top: 2px; }
  
  .stats { text-align: right; min-width: 80px; }
  .time-val { font-size: 1.6rem; font-weight: 900; color: var(--primary-text-color); }
  .time-unit { font-size: 0.75rem; color: var(--secondary-text-color); font-weight: 700; text-transform: uppercase; }

  /* Pasek Postępu (Wykres) */
  .progress-container {
    width: 100%;
    height: 6px;
    background-color: #f0f0f0;
    border-radius: 3px;
    margin-bottom: 12px;
    overflow: hidden;
  }
  .progress-bar {
    height: 100%;
    background-color: #4CAF50;
    border-radius: 3px;
    transition: width 0.5s ease-in-out;
  }

  .sensors-row { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 12px; border-top: 2px solid #f0f0f0; }
  .sensor-chip { 
    display: inline-flex; align-items: center; 
    background: var(--secondary-background-color); 
    padding: 6px 12px; border-radius: 20px; 
    font-size: 0.9rem; 
    font-weight: 600;
    color: var(--primary-text-color); 
    border: 1px solid var(--divider-color, #ddd);
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }
  .sensor-chip ha-icon { --mdc-icon-size: 18px; margin-right: 6px; color: var(--secondary-text-color); }
`;

function renderEmployeeHTML(hass, entityId) {
  const statusEntity = hass.states[entityId];
  if (!statusEntity) return '';

  const fullName = statusEntity.attributes.friendly_name.replace(' - Status', '');
  const baseId = entityId.replace('_status', '');
  const state = statusEntity.state;

  const timeEntity = hass.states[`${baseId}_czas_pracy`];
  const timeVal = timeEntity ? Math.round(parseFloat(timeEntity.state)) : 0;

  // --- LOGIKA 8 GODZIN ---
  const isOvertime = timeVal > 480; // 8h * 60min

  let statusClass = 'is-absent';
  let iconName = 'mdi:account-off';

  if (state === 'Pracuje') {
    statusClass = 'is-working';
    iconName = 'mdi:laptop';
    if (isOvertime) { statusClass = 'is-overtime'; iconName = 'mdi:fire'; } // Efekt nadgodzin
  }
  else if (state === 'Obecny (Idle)') { statusClass = 'is-idle'; iconName = 'mdi:coffee'; }

  // Pasek
  let progressPct = (timeVal / 480) * 100;
  let progressClass = "";
  if (progressPct > 100) { progressPct = 100; progressClass = "over"; }

  // ... (reszta renderowania sensorów bez zmian) ...

  return `
    <div class="emp-card">
      <div class="header">
        <div class="icon-box ${statusClass}"><ha-icon icon="${iconName}"></ha-icon></div>
        <div class="info">
          <div class="emp-name">${fullName}</div>
          <div class="emp-status">${isOvertime && state == 'Pracuje' ? 'NADGODZINY 🔥' : state}</div>
          <div style="font-size:0.75em; color:#999">${statusEntity.attributes.group || ''}</div>
        </div>
        <div class="stats"><div class="time-val">${timeVal}</div><div class="time-unit">MINUT</div></div>
      </div>
      <div class="progress-container"><div class="progress-bar ${progressClass}" style="width: ${progressPct}%"></div></div>
      <div class="sensors-row">${sensorsHtml}</div>
    </div>`;
}

// --- KARTA DASHBOARD Z FILTREM GRUP ---
class EmployeeDashboard extends HTMLElement {
  setConfig(config) {
    this.config = config;
    this.title = config.title || (config.group ? `Zespół: ${config.group}` : "Wszyscy");
  }

  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `...style... <div class="dash-title">${this.title}</div><div id="d"></div>`;
      this.content = this.querySelector('#d');
    }

    // Pobieramy wszystkich pracowników
    let employees = Object.keys(hass.states)
      .filter(eid => eid.startsWith('sensor.') && eid.endsWith('_status'));

    // --- FILTROWANIE PO GRUPIE ---
    if (this.config.group) {
      employees = employees.filter(eid => {
        const attr = hass.states[eid].attributes;
        return attr && attr.group === this.config.group;
      });
    }

    employees.sort();

    if (employees.length === 0) {
      this.content.innerHTML = "Brak pracowników w tej grupie."; return;
    }
    this.content.innerHTML = employees.map(eid => renderEmployeeHTML(hass, eid)).join('');
  }
}

class EmployeeCard extends HTMLElement {
  setConfig(config) {
    if (!config.name) throw new Error('Podaj imię!');
    this.config = config;
  }
  set hass(hass) {
    const id = this.config.name.toLowerCase().trim().replace(/ /g, "_").replace(/ą/g, 'a').replace(/ć/g, 'c').replace(/ę/g, 'e').replace(/ł/g, 'l').replace(/ń/g, 'n').replace(/ó/g, 'o').replace(/ś/g, 's').replace(/ź/g, 'z').replace(/ż/g, 'z');
    const entityId = `sensor.${id}_status`;
    if (!this.content) {
      this.innerHTML = `<style>${SHARED_STYLES}</style><div id="card-content"></div>`;
      this.content = this.querySelector('#card-content');
    }
    this.content.innerHTML = renderEmployeeHTML(hass, entityId);
  }
  getCardSize() { return 1; }
  static getStubConfig() { return { name: "Jan" }; }
  static getConfigElement() { return document.createElement("employee-card-editor"); }
}

class EmployeeDashboard extends HTMLElement {
  setConfig(config) { this.config = config; this.title = config.title || "Zespół"; }
  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
        <style>
          ${SHARED_STYLES}
          .dashboard-container { display: flex; flex-direction: column; }
          .dash-title { font-size: 1.4rem; font-weight: 800; margin-bottom: 15px; color: var(--primary-text-color); padding-left: 5px; }
        </style>
        <div class="dash-title">${this.title}</div>
        <div id="dashboard-content" class="dashboard-container">Ładowanie...</div>
      `;
      this.content = this.querySelector('#dashboard-content');
    }
    const employees = Object.keys(hass.states)
      .filter(eid => eid.startsWith('sensor.') && eid.endsWith('_status'))
      .sort();

    if (employees.length === 0) {
      this.content.innerHTML = "<div style='padding:20px;text-align:center;opacity:0.6'>Brak pracowników.<br>Dodaj ich w panelu Employee Manager.</div>";
      return;
    }
    this.content.innerHTML = employees.map(eid => renderEmployeeHTML(hass, eid)).join('');
  }
  getCardSize() { return 3; }
}

class EmployeeCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this.render(); }
  render() {
    if (!this.innerHTML) {
      this.innerHTML = `
        <div class="card-config" style="padding:20px;">
          <label style="font-weight:bold">Imię Pracownika</label>
          <input type="text" id="name-input" style="width:100%; padding:8px; margin-top:5px;">
        </div>`;
      this.querySelector('#name-input').addEventListener('input', (e) =>
        this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: { ...this._config, name: e.target.value } }, bubbles: true, composed: true }))
      );
    }
    this.querySelector('#name-input').value = this._config.name || '';
  }
}

customElements.define('employee-card-editor', EmployeeCardEditor);
customElements.define('employee-card', EmployeeCard);
customElements.define('employee-dashboard', EmployeeDashboard);

window.customCards = window.customCards || [];
window.customCards.push({ type: "employee-card", name: "Pracownik (Pojedynczy)", description: "Karta jednego pracownika" });
window.customCards.push({ type: "employee-dashboard", name: "Panel Zespołu (AUTO)", preview: true, description: "Automatycznie wyświetla wszystkich pracowników" });