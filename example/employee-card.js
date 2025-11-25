// --- KONFIGURACJA: Co karta ma wykrywać ---
const KNOWN_SENSOR_TYPES = [
  { suffix: 'temperatura', icon: 'mdi:thermometer', unit: '°C' },
  { suffix: 'wilgotnosc', icon: 'mdi:water-percent', unit: '%' },
  { suffix: 'cisnienie', icon: 'mdi:gauge', unit: 'hPa' },
  { suffix: 'moc', icon: 'mdi:lightning-bolt', unit: 'W' },
  { suffix: 'napiecie', icon: 'mdi:sine-wave', unit: 'V' },
  { suffix: 'natezenie', icon: 'mdi:current-ac', unit: 'A' },
  { suffix: 'bateria', icon: 'mdi:battery', unit: '%' }
];

// --- WSPÓLNE STYLE CSS ---
const SHARED_STYLES = `
  .emp-card { 
    background: var(--ha-card-background, white); 
    border-radius: 12px; 
    box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1)); 
    padding: 16px; 
    border: 1px solid var(--divider-color, #eee);
    margin-bottom: 12px;
    transition: transform 0.1s;
  }
  .emp-card:hover { transform: scale(1.01); }
  
  .header { display: flex; align-items: center; width: 100%; margin-bottom: 12px; }
  
  .icon-box { width: 45px; height: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; background: #eee; color: #555; }
  
  .is-working { background: rgba(76, 175, 80, 0.15); color: #2E7D32; border: 2px solid rgba(76, 175, 80, 0.3); }
  .is-idle { background: rgba(255, 193, 7, 0.15); color: #F57F17; border: 2px solid rgba(255, 193, 7, 0.3); }
  .is-absent { background: rgba(244, 67, 54, 0.1); color: #C62828; }

  .info { flex: 1; }
  .emp-name { font-weight: 700; font-size: 1.1rem; }
  .emp-status { font-size: 0.85rem; opacity: 0.8; }
  
  .stats { text-align: right; min-width: 70px; }
  .time-val { font-size: 1.3rem; font-weight: 800; color: var(--primary-text-color); }
  .time-unit { font-size: 0.7rem; opacity: 0.6; text-transform: uppercase; }

  .sensors-row { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 10px; border-top: 1px solid var(--divider-color, #eee); }
  .sensor-chip { 
    display: inline-flex; align-items: center; background: var(--secondary-background-color, #f5f5f5); 
    padding: 4px 10px; border-radius: 8px; font-size: 0.85rem; color: var(--primary-text-color); border: 1px solid var(--divider-color, #eee);
  }
  .sensor-chip ha-icon { --mdc-icon-size: 16px; margin-right: 6px; opacity: 0.7; }
`;

// --- HELPER: Generowanie HTML dla jednego pracownika ---
function renderEmployeeHTML(hass, entityId) {
  const statusEntity = hass.states[entityId];
  if (!statusEntity) return '';

  // Ustalanie nazw
  const fullName = statusEntity.attributes.friendly_name.replace(' - Status', '');
  const baseId = entityId.replace('_status', '');
  
  // Status
  const state = statusEntity.state;
  let statusClass = 'is-absent';
  let iconName = 'mdi:account-off';
  
  if (state === 'Pracuje') { statusClass = 'is-working'; iconName = 'mdi:laptop'; }
  else if (state === 'Obecny (Idle)') { statusClass = 'is-idle'; iconName = 'mdi:coffee'; }

  // Czas
  const timeEntity = hass.states[`${baseId}_czas_pracy`];
  const timeVal = timeEntity ? Math.round(parseFloat(timeEntity.state)) : '--';

  // Sensory dodatkowe
  let sensorsHtml = '';
  KNOWN_SENSOR_TYPES.forEach(type => {
    const sId = `${baseId}_${type.suffix}`;
    const sEnt = hass.states[sId];
    if (sEnt && sEnt.state !== 'unavailable' && sEnt.state !== 'unknown') {
      const unit = sEnt.attributes.unit_of_measurement || type.unit;
      sensorsHtml += `
        <div class="sensor-chip">
          <ha-icon icon="${type.icon}"></ha-icon>
          <span>${sEnt.state} ${unit}</span>
        </div>`;
    }
  });

  return `
    <div class="emp-card">
      <div class="header">
        <div class="icon-box ${statusClass}"><ha-icon icon="${iconName}"></ha-icon></div>
        <div class="info">
          <div class="emp-name">${fullName}</div>
          <div class="emp-status">${state}</div>
        </div>
        <div class="stats">
          <div class="time-val">${timeVal}</div>
          <div class="time-unit">MINUT</div>
        </div>
      </div>
      ${sensorsHtml ? `<div class="sensors-row">${sensorsHtml}</div>` : ''}
    </div>
  `;
}

// ============================================================
// 1. KARTA POJEDYNCZA (Single)
// ============================================================
class EmployeeCard extends HTMLElement {
  setConfig(config) {
    if (!config.name) throw new Error('Podaj imię!');
    this.config = config;
  }

  set hass(hass) {
    const id = this.config.name.toLowerCase().replace(/ /g, "_").replace(/ą/g,'a').replace(/ć/g,'c').replace(/ę/g,'e').replace(/ł/g,'l').replace(/ń/g,'n').replace(/ó/g,'o').replace(/ś/g,'s').replace(/ź/g,'z').replace(/ż/g,'z');
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

// ============================================================
// 2. KARTA ZBIORCZA (Dashboard - Auto)
// ============================================================
class EmployeeDashboard extends HTMLElement {
  setConfig(config) {
    this.config = config;
    this.title = config.title || "Zespół";
  }

  set hass(hass) {
    if (!this.content) {
      this.innerHTML = `
        <style>
          ${SHARED_STYLES}
          .dashboard-container { display: flex; flex-direction: column; }
          .dash-title { font-size: 1.2rem; font-weight: bold; margin-bottom: 10px; color: var(--primary-text-color); padding-left: 5px; }
        </style>
        <div class="dash-title">${this.title}</div>
        <div id="dashboard-content" class="dashboard-container">Ładowanie...</div>
      `;
      this.content = this.querySelector('#dashboard-content');
    }

    // Skanujemy system w poszukiwaniu pracowników
    const employees = Object.keys(hass.states)
      .filter(eid => eid.startsWith('sensor.') && eid.endsWith('_status'))
      .sort();

    if (employees.length === 0) {
      this.content.innerHTML = "<div style='padding:20px;text-align:center;opacity:0.6'>Brak pracowników.<br>Dodaj ich w panelu Employee Manager.</div>";
      return;
    }

    // Generujemy HTML dla każdego znalezionego pracownika
    this.content.innerHTML = employees.map(eid => renderEmployeeHTML(hass, eid)).join('');
  }
  getCardSize() { return 3; }
}

// --- EDYTOR DLA POJEDYNCZEJ KARTY ---
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

// --- REJESTRACJA ---
customElements.define('employee-card-editor', EmployeeCardEditor);
customElements.define('employee-card', EmployeeCard);
customElements.define('employee-dashboard', EmployeeDashboard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "employee-card",
  name: "Pracownik (Pojedynczy)",
  description: "Karta jednego pracownika"
});
window.customCards.push({
  type: "employee-dashboard",
  name: "Panel Zespołu (AUTO)",
  preview: true,
  description: "Automatycznie wyświetla wszystkich pracowników"
});