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
    transition: transform 0.1s;
    height: 100%;
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
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
  .emp-group { font-size: 0.75rem; color: var(--secondary-text-color); background: var(--secondary-background-color); padding: 2px 8px; border-radius: 4px; display: inline-block; margin-top: 4px; border: 1px solid var(--divider-color); }

  .stats { text-align: right; min-width: 80px; }
  .time-val { font-size: 1.6rem; font-weight: 900; color: var(--primary-text-color); }
  .time-unit { font-size: 0.75rem; color: var(--secondary-text-color); font-weight: 700; text-transform: uppercase; }

  .progress-container { width: 100%; height: 6px; background-color: #f0f0f0; border-radius: 3px; margin-bottom: 12px; overflow: hidden; }
  .progress-bar { height: 100%; background-color: #4CAF50; border-radius: 3px; transition: width 0.5s ease-in-out; }
  .progress-bar.over { background-color: #9C27B0; }

  .sensors-row { display: flex; flex-wrap: wrap; gap: 8px; padding-top: 12px; border-top: 1px solid var(--divider-color, #eee); }
  .sensor-chip { 
    display: inline-flex; align-items: center; 
    background: var(--secondary-background-color); 
    padding: 6px 12px; border-radius: 20px; 
    font-size: 0.9rem; font-weight: 600;
    color: var(--primary-text-color); 
    border: 1px solid var(--divider-color, #ddd);
    box-shadow: 0 1px 2px rgba(0,0,0,0.05);
  }
  .sensor-chip ha-icon { --mdc-icon-size: 18px; margin-right: 6px; color: var(--secondary-text-color); }

  .filter-bar { display: flex; gap: 8px; overflow-x: auto; padding-bottom: 10px; margin-bottom: 10px; scrollbar-width: none; }
  .filter-btn {
    border: none; background: var(--card-background-color); 
    box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,0.1));
    padding: 8px 16px; border-radius: 20px; font-weight: 600; color: var(--primary-text-color);
    cursor: pointer; white-space: nowrap; transition: all 0.2s;
    border: 1px solid var(--divider-color, transparent);
  }
  .filter-btn:hover { background: var(--secondary-background-color); }
  .filter-btn.active { background: var(--primary-color); color: white; }
`;

function renderEmployeeHTML(hass, entityId) {
  const statusEntity = hass.states[entityId];
  if (!statusEntity) return '';

  const fullName = statusEntity.attributes.friendly_name.replace(' - Status', '');
  const groupName = statusEntity.attributes.group || 'Domyślna';
  const baseId = entityId.replace('_status', '');
  const state = statusEntity.state;

  let statusClass = 'is-absent', iconName = 'mdi:account-off';
  if (state === 'Pracuje') { statusClass = 'is-working'; iconName = 'mdi:laptop'; }
  else if (state.includes('Idle') || state.includes('Obecny')) { statusClass = 'is-idle'; iconName = 'mdi:coffee'; }

  const timeEntity = hass.states[`${baseId}_czas_pracy`];
  const timeVal = timeEntity ? Math.round(parseFloat(timeEntity.state)) : 0;

  const targetMinutes = 480;
  let progressPct = (timeVal / targetMinutes) * 100;
  let progressClass = "";
  if (progressPct > 100) { progressPct = 100; progressClass = "over"; }

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
    <div class="emp-card" data-group="${groupName}">
      <div class="header">
        <div class="icon-box ${statusClass}"><ha-icon icon="${iconName}"></ha-icon></div>
        <div class="info">
          <div class="emp-name">${fullName}</div>
          <div class="emp-status">${state}</div>
          <div class="emp-group">${groupName}</div>
        </div>
        <div class="stats">
          <div class="time-val">${timeVal}</div>
          <div class="time-unit">MINUT</div>
        </div>
      </div>
      <div class="progress-container" title="Cel: 8h"><div class="progress-bar ${progressClass}" style="width: ${progressPct}%"></div></div>
      
      ${sensorsHtml ? `<div class="sensors-row">${sensorsHtml}</div>` : ''}
    </div>
  `;
}

class EmployeeDashboard extends HTMLElement {
  setConfig(config) {
    this.config = config;
    this.title = config.title || "Zespół";
    this.currentFilter = 'Wszyscy';
  }

  set hass(hass) {
    this._hass = hass;

    if (!this.content) {
      this.innerHTML = `
        <style>
          ${SHARED_STYLES}
          .dashboard-container { 
            display: grid; 
            grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); 
            gap: 16px; 
          }
          .dash-title { font-size: 1.4rem; font-weight: 800; margin-bottom: 15px; color: var(--primary-text-color); padding-left: 5px; }
        </style>
        <div class="dash-title">${this.title}</div>
        <div id="filters" class="filter-bar"></div>
        <div id="dashboard-content" class="dashboard-container">Ładowanie...</div>
      `;
      this.content = this.querySelector('#dashboard-content');
      this.filtersContainer = this.querySelector('#filters');
    }

    this.render();
  }

  render() {
    const hass = this._hass;
    const employees = Object.keys(hass.states)
      .filter(eid => eid.startsWith('sensor.') && eid.endsWith('_status'))
      .sort();

    if (employees.length === 0) {
      this.content.innerHTML = "<div style='padding:20px;opacity:0.6'>Brak pracowników.</div>";
      return;
    }

    const groups = new Set(['Wszyscy']);
    employees.forEach(eid => {
      const g = hass.states[eid].attributes.group;
      if (g) groups.add(g);
    });

    this.filtersContainer.innerHTML = '';
    groups.forEach(g => {
      const btn = document.createElement('button');
      btn.innerText = g;
      btn.className = `filter-btn ${this.currentFilter === g ? 'active' : ''}`;

      btn.onclick = () => {
        this.currentFilter = g;
        this.render();
      };

      this.filtersContainer.appendChild(btn);
    });

    const filtered = employees.filter(eid => {
      if (this.currentFilter === 'Wszyscy') return true;
      return hass.states[eid].attributes.group === this.currentFilter;
    });

    if (filtered.length === 0) {
      this.content.innerHTML = `<div style='padding:20px;opacity:0.6'>Brak pracowników w grupie ${this.currentFilter}.</div>`;
    } else {
      this.content.innerHTML = filtered.map(eid => renderEmployeeHTML(hass, eid)).join('');
    }
  }
  getCardSize() { return 3; }
}

class EmployeeCard extends HTMLElement {
  setConfig(c) { if (!c.name) throw new Error('Podaj imię!'); this.config = c; }
  set hass(hass) {
    const id = this.config.name.toLowerCase().trim().replace(/ /g, "_");
    const keys = Object.keys(hass.states);
    const entityId = keys.find(k => k.includes(id) && k.endsWith('_status'));

    if (!this.content) {
      this.innerHTML = `<style>${SHARED_STYLES}</style><div id="card-content"></div>`;
      this.content = this.querySelector('#card-content');
    }
    if (entityId) this.content.innerHTML = renderEmployeeHTML(hass, entityId);
    else this.content.innerHTML = `Nie znaleziono pracownika: ${this.config.name}`;
  }
  getCardSize() { return 1; }
  static getConfigElement() { return document.createElement("employee-card-editor"); }
  static getStubConfig() { return { name: "Jan" }; }
}

class EmployeeCardEditor extends HTMLElement {
  setConfig(c) { this._config = c; this.render(); }
  render() {
    if (!this.innerHTML) {
      this.innerHTML = `<div class="card-config" style="padding:20px;"><label style="font-weight:bold">Imię Pracownika</label><input type="text" id="name-input" style="width:100%; padding:8px; margin-top:5px;"></div>`;
      this.querySelector('#name-input').addEventListener('input', (e) => this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: { ...this._config, name: e.target.value } }, bubbles: true, composed: true })));
    }
    this.querySelector('#name-input').value = this._config.name || '';
  }
}

customElements.define('employee-card-editor', EmployeeCardEditor);
customElements.define('employee-card', EmployeeCard);
customElements.define('employee-dashboard', EmployeeDashboard);

window.customCards = window.customCards || [];
window.customCards.push({ type: "employee-card", name: "Pracownik (Pojedynczy)", description: "Jeden kafelek" });
window.customCards.push({ type: "employee-dashboard", name: "Panel Zespołu (AUTO)", preview: true, description: "Automatycznie wyświetla wszystkich pracowników" });