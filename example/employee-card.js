class EmployeeCard extends HTMLElement {
  setConfig(config) {
    if (!config.name) {
      throw new Error('Wpisz imię pracownika!');
    }
    this.config = config;
  }

  set hass(hass) {
    const name = this.config.name;
    // Konwersja imienia na ID
    const id = name.toLowerCase().replace(/ /g, "_")
                   .replace(/ą/g, 'a').replace(/ć/g, 'c').replace(/ę/g, 'e')
                   .replace(/ł/g, 'l').replace(/ń/g, 'n').replace(/ó/g, 'o')
                   .replace(/ś/g, 's').replace(/ź/g, 'z').replace(/ż/g, 'z');

    // Główne sensory
    const statusEntity = hass.states[`sensor.${id}_status`];
    const timeEntity = hass.states[`sensor.${id}_czas_pracy`];

    // Lista potencjalnych dodatkowych czujników do sprawdzenia
    const potentialSensors = [
      { suffix: 'temperatura', icon: 'mdi:thermometer', unit: '°C' },
      { suffix: 'wilgotnosc', icon: 'mdi:water-percent', unit: '%' },
      { suffix: 'cisnienie', icon: 'mdi:gauge', unit: 'hPa' }
    ];

    // Rysowanie szkieletu (raz)
    if (!this.content) {
      this.innerHTML = `
        <style>
          ha-card { padding: 16px; display: flex; flex-direction: column; cursor: pointer; transition: all 0.2s; }
          ha-card:hover { box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
          
          .header { display: flex; align-items: center; width: 100%; margin-bottom: 10px; }
          .icon-container { width: 45px; height: 45px; border-radius: 50%; display: flex; align-items: center; justify-content: center; margin-right: 15px; background: #eee; color: #555; }
          
          .status-working { background: rgba(76, 175, 80, 0.2); color: #2E7D32; }
          .status-idle { background: rgba(255, 193, 7, 0.2); color: #F57F17; }
          .status-absent { background: rgba(244, 67, 54, 0.2); color: #C62828; }

          .info { flex: 1; }
          .name { font-weight: 600; font-size: 1.1rem; }
          .status-text { font-size: 0.85rem; opacity: 0.8; }
          .stats { text-align: right; }
          .time-val { font-size: 1.2rem; font-weight: bold; }
          .time-unit { font-size: 0.7rem; opacity: 0.7; }

          /* Sekcja dodatkowych czujników */
          .sensors-row { 
            display: flex; 
            width: 100%; 
            border-top: 1px solid #eee; 
            padding-top: 10px; 
            gap: 10px;
            justify-content: flex-start;
          }
          .sensor-chip {
            display: flex; align-items: center; 
            background: #f5f5f5; 
            padding: 4px 8px; 
            border-radius: 12px; 
            font-size: 0.85rem;
            color: #444;
          }
          .sensor-chip ha-icon { --mdc-icon-size: 16px; margin-right: 4px; color: #666; }
        </style>
        <ha-card>
          <div class="header">
            <div class="icon-container" id="icon"><ha-icon icon="mdi:account"></ha-icon></div>
            <div class="info"><div class="name"></div><div class="status-text" id="status">Brak Danych</div></div>
            <div class="stats"><div class="time-val" id="time">--</div><div class="time-unit">MINUT</div></div>
          </div>
          <div class="sensors-row" id="sensors-container"></div>
        </ha-card>
      `;
      this.content = this.querySelector('ha-card');
      this.querySelector('.name').innerText = name;
    }

    // Aktualizacja Statusu i Czasu
    if (statusEntity) {
      const state = statusEntity.state;
      const iconDiv = this.querySelector('#icon');
      
      this.querySelector('#status').innerText = state;
      
      iconDiv.className = 'icon-container';
      let iconName = 'mdi:account-off';
      if (state === 'Pracuje') { iconDiv.classList.add('status-working'); iconName = 'mdi:laptop'; }
      else if (state === 'Obecny (Idle)') { iconDiv.classList.add('status-idle'); iconName = 'mdi:coffee'; }
      else { iconDiv.classList.add('status-absent'); }
      this.querySelector('#icon ha-icon').setAttribute('icon', iconName);
    }

    if (timeEntity) {
      this.querySelector('#time').innerText = timeEntity.state;
    }

    // Aktualizacja Dodatkowych Czujników (Temp/Wilg/Ciśnienie)
    const sensorsDiv = this.querySelector('#sensors-container');
    sensorsDiv.innerHTML = ''; // Czyścimy stare
    
    potentialSensors.forEach(s => {
      const entity = hass.states[`sensor.${id}_${s.suffix}`];
      if (entity && entity.state !== 'unavailable' && entity.state !== 'unknown') {
        sensorsDiv.innerHTML += `
          <div class="sensor-chip">
            <ha-icon icon="${s.icon}"></ha-icon>
            <span>${entity.state} ${s.unit}</span>
          </div>
        `;
      }
    });
  }

  getCardSize() { return 1; }

  static getStubConfig() { return { name: "Marek" }; }
  static getConfigElement() { return document.createElement("employee-card-editor"); }
}

class EmployeeCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this.render(); }
  render() {
    if (!this.innerHTML) {
      this.innerHTML = `
        <div class="card-config">
          <div class="input-container" style="padding: 20px 0;">
            <label style="display:block; margin-bottom: 8px; font-weight:bold;">Imię Pracownika</label>
            <input type="text" id="name-input" placeholder="np. Maurycy" style="width: 95%; padding: 10px; border: 1px solid #ccc; border-radius: 4px;">
          </div>
        </div>`;
      this.querySelector('#name-input').addEventListener('input', (e) => this._valueChanged(e.target.value));
    }
    this.querySelector('#name-input').value = this._config.name || '';
  }
  _valueChanged(newVal) {
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: { ...this._config, name: newVal } }, bubbles: true, composed: true }));
  }
}

customElements.define('employee-card-editor', EmployeeCardEditor);
customElements.define('employee-card', EmployeeCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: "employee-card",
  name: "Karta Pracownika (Full)",
  preview: true,
  description: "Karta ze statusem i pomiarami"
});