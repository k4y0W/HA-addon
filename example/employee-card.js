const KNOWN_SENSOR_TYPES = [
  { suffix: 'temperatura', icon: 'mdi:thermometer', unit: '°C' },
  { suffix: 'wilgotnosc', icon: 'mdi:water-percent', unit: '%' },
  { suffix: 'cisnienie', icon: 'mdi:gauge', unit: 'hPa' },
  { suffix: 'moc', icon: 'mdi:lightning-bolt', unit: 'W' },
  { suffix: 'napiecie', icon: 'mdi:sine-wave', unit: 'V' },
  { suffix: 'natezenie', icon: 'mdi:current-ac', unit: 'A' },
  { suffix: 'bateria', icon: 'mdi:battery', unit: '%' },
  { suffix: 'pm25', icon: 'mdi:blur', unit: 'μg/m³' }
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
  
  /* Bardziej nasycone kolory statusów */
  .is-working { background: #E8F5E9; color: #1B5E20; border: 2px solid #4CAF50; }
  .is-idle { background: #FFFDE7; color: #E65100; border: 2px solid #FFC107; }
  .is-absent { background: #FFEBEE; color: #B71C1C; border: 2px solid #EF5350; }

  .info { flex: 1; }
  /* Ciemniejsze, większe czcionki */
  .emp-name { 
    font-weight: 800; 
    font-size: 1.3rem; 
    color: #111; /* Prawie czarny */
    line-height: 1.2;
  }
  .emp-status { 
    font-size: 1rem; 
    color: #444; /* Ciemny szary */
    font-weight: 600;
    margin-top: 2px;
  }
  
  .stats { text-align: right; min-width: 80px; }
  .time-val { 
    font-size: 1.6rem; 
    font-weight: 900; 
    color: #000; /* Czarny */
  }
  .time-unit { 
    font-size: 0.75rem; 
    color: #555; 
    font-weight: 700; 
    text-transform: uppercase; 
  }

  .sensors-row { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 12px; border-top: 2px solid #f0f0f0; }
  .sensor-chip { 
    display: inline-flex; align-items: center; 
    background: #f8f9fa; 
    padding: 6px 12px; border-radius: 20px; 
    font-size: 0.9rem; 
    font-weight: 600;
    color: #333; /* Ciemny tekst na chipach */
    border: 1px solid #ddd;
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }
  .sensor-chip ha-icon { --mdc-icon-size: 18px; margin-right: 6px; color: #555; }
`;

function renderEmployeeHTML(hass, entityId) {
  const statusEntity = hass.states[entityId];
  if (!statusEntity) return '';

  const fullName = statusEntity.attributes.friendly_name.replace(' - Status', '');
  const baseId = entityId.replace('_status', '');
  
  const state = statusEntity.state;
  let statusClass = 'is-absent';
  let iconName = 'mdi:account-off';
  
  if (state === 'Pracuje') { statusClass = 'is-working'; iconName = 'mdi:laptop'; }
  else if (state === 'Obecny (Idle)') { statusClass = 'is-idle'; iconName = 'mdi:coffee'; }

  const timeEntity = hass.states[`${baseId}_czas_pracy`];
  const timeVal = timeEntity ? Math.round(parseFloat(timeEntity.state)) : '--';

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

class EmployeeCard extends HTMLElement {
  setConfig(config) {
    if (!config.name) throw new Error('Podaj imię!');
    this.config = config;
  }
  set hass(hass) {
    const id = this.config.name.toLowerCase().trim().replace(/ /g, "_").replace(/ą/g,'a').replace(/ć/g,'c').replace(/ę/g,'e').replace(/ł/g,'l').replace(/ń/g,'n').replace(/ó/g,'o').replace(/ś/g,'s').replace(/ź/g,'z').replace(/ż/g,'z');
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