// Definicja znanych typów czujników (musi pasować do tego co masz w mapie Pythona)
// Karta sprawdzi, czy dany pracownik ma te sensory.
const KNOWN_SENSOR_TYPES = [
  { suffix: 'temperatura', icon: 'mdi:thermometer', unit: '°C' },
  { suffix: 'wilgotnosc', icon: 'mdi:water-percent', unit: '%' },
  { suffix: 'cisnienie', icon: 'mdi:gauge', unit: 'hPa' },
  { suffix: 'moc', icon: 'mdi:lightning-bolt', unit: 'W' },         // Na przyszłość
  { suffix: 'napiecie', icon: 'mdi:sine-wave', unit: 'V' },         // Na przyszłość
  { suffix: 'natezenie', icon: 'mdi:current-ac', unit: 'A' }        // Na przyszłość
];

class EmployeeCard extends HTMLElement {
  setConfig(config) {
    if (!config.name) {
      throw new Error('Wpisz imię pracownika w edytorze!');
    }
    this.config = config;
  }

  set hass(hass) {
    const name = this.config.name;
    
    // 1. Generowanie bezpiecznego ID (Jan Kowalski -> jan_kowalski)
    // Ta funkcja musi działać identycznie jak w Pythonie!
    const id = name.toLowerCase().trim()
                   .replace(/ /g, "_")
                   .replace(/ą/g, 'a').replace(/ć/g, 'c').replace(/ę/g, 'e')
                   .replace(/ł/g, 'l').replace(/ń/g, 'n').replace(/ó/g, 'o')
                   .replace(/ś/g, 's').replace(/ź/g, 'z').replace(/ż/g, 'z');

    // 2. Pobieranie głównych stanów
    const statusEntity = hass.states[`sensor.${id}_status`];
    const timeEntity = hass.states[`sensor.${id}_czas_pracy`];

    // 3. Rysowanie szkieletu HTML (tylko raz)
    if (!this.content) {
      this.innerHTML = `
        <style>
          ha-card { 
            padding: 16px; 
            display: flex; 
            flex-direction: column; 
            cursor: pointer; 
            transition: transform 0.1s ease-in-out;
            border-radius: 12px;
          }
          ha-card:active { transform: scale(0.98); }
          
          /* Górna sekcja: Ikonka, Imię, Status */
          .header { display: flex; align-items: center; width: 100%; margin-bottom: 12px; }
          
          .icon-box { 
            width: 48px; height: 48px; 
            border-radius: 50%; 
            display: flex; align-items: center; justify-content: center; 
            margin-right: 16px; 
            background: #f0f0f0; color: #555;
            transition: background 0.3s;
          }
          
          /* Kolory statusów */
          .is-working { background: rgba(76, 175, 80, 0.15); color: #2E7D32; border: 2px solid rgba(76, 175, 80, 0.3); }
          .is-idle { background: rgba(255, 193, 7, 0.15); color: #F57F17; border: 2px solid rgba(255, 193, 7, 0.3); }
          .is-absent { background: rgba(244, 67, 54, 0.1); color: #C62828; }

          .info-box { flex: 1; }
          .emp-name { font-weight: 700; font-size: 1.15rem; line-height: 1.2; }
          .emp-status { font-size: 0.9rem; opacity: 0.85; font-weight: 500; }
          
          .time-box { text-align: right; min-width: 70px; }
          .time-val { font-size: 1.4rem; font-weight: 800; color: #333; }
          .time-unit { font-size: 0.7rem; text-transform: uppercase; letter-spacing: 0.5px; opacity: 0.6; }

          /* Dolna sekcja: Chipy z sensorami */
          .sensors-grid { 
            display: flex; 
            flex-wrap: wrap;
            gap: 8px;
            padding-top: 12px;
            border-top: 1px solid #eee;
          }
          .sensor-chip {
            display: inline-flex; 
            align-items: center; 
            background: #f8f9fa; 
            padding: 4px 10px; 
            border-radius: 8px; 
            font-size: 0.85rem;
            color: #444;
            border: 1px solid #eee;
          }
          .sensor-chip ha-icon { 
            --mdc-icon-size: 16px; 
            margin-right: 6px; 
            color: #666;
          }
        </style>
        
        <ha-card>
          <div class="header">
            <div class="icon-box" id="main-icon"><ha-icon icon="mdi:account"></ha-icon></div>
            <div class="info-box">
              <div class="emp-name"></div>
              <div class="emp-status" id="status-text">Wczytywanie...</div>
            </div>
            <div class="time-box">
              <div class="time-val" id="time-val">--</div>
              <div class="time-unit">MINUT</div>
            </div>
          </div>
          
          <div class="sensors-grid" id="sensors-container"></div>
        </ha-card>
      `;
      this.content = this.querySelector('ha-card');
      this.querySelector('.emp-name').innerText = name;
    }

    // 4. Aktualizacja Statusu
    if (statusEntity) {
      const state = statusEntity.state;
      this.querySelector('#status-text').innerText = state;
      
      const iconBox = this.querySelector('#main-icon');
      const haIcon = this.querySelector('#main-icon ha-icon');
      
      // Reset klas
      iconBox.className = 'icon-box';
      
      if (state === 'Pracuje') { 
        iconBox.classList.add('is-working'); 
        haIcon.setAttribute('icon', 'mdi:laptop');
      } else if (state === 'Obecny (Idle)') { 
        iconBox.classList.add('is-idle'); 
        haIcon.setAttribute('icon', 'mdi:coffee');
      } else { 
        iconBox.classList.add('is-absent'); 
        haIcon.setAttribute('icon', 'mdi:account-off');
      }
    }

    // 5. Aktualizacja Czasu
    if (timeEntity) {
      this.querySelector('#time-val').innerText = Math.round(parseFloat(timeEntity.state));
    }

    // 6. Pętla po znanych typach sensorów (Autowykrywanie)
    const sensorsContainer = this.querySelector('#sensors-container');
    sensorsContainer.innerHTML = ''; // Czyścimy, żeby nie dublować przy odświeżaniu

    let foundAny = false;
    KNOWN_SENSOR_TYPES.forEach(type => {
      // Budujemy przewidywane ID: sensor.jan_temperatura
      const sensorId = `sensor.${id}_${type.suffix}`;
      const entity = hass.states[sensorId];

      // Jeśli taka encja istnieje w HA i ma wartość
      if (entity && entity.state !== 'unavailable' && entity.state !== 'unknown') {
        foundAny = true;
        const val = entity.state;
        const unit = entity.attributes.unit_of_measurement || type.unit;
        
        sensorsContainer.innerHTML += `
          <div class="sensor-chip">
            <ha-icon icon="${type.icon}"></ha-icon>
            <span>${val} ${unit}</span>
          </div>
        `;
      }
    });

    // Jeśli brak sensorów, ukryj dolną sekcję (żeby nie było pustego paska)
    if (!foundAny) {
      sensorsContainer.style.display = 'none';
    } else {
      sensorsContainer.style.display = 'flex';
    }
  }

  getCardSize() { return 1; }

  // Konfiguracja Edytora
  static getStubConfig() { return { name: "Jan" }; }
  static getConfigElement() { return document.createElement("employee-card-editor"); }
}

// Klasa Edytora (Formularz wpisywania imienia)
class EmployeeCardEditor extends HTMLElement {
  setConfig(config) { this._config = config; this.render(); }
  render() {
    if (!this.innerHTML) {
      this.innerHTML = `
        <div class="card-config">
          <div class="input-container" style="padding: 20px 0;">
            <label style="display:block; margin-bottom: 8px; font-weight:bold;">Imię Pracownika</label>
            <input type="text" id="name-input" placeholder="Wpisz imię z konfiguracji Add-onu" style="width: 95%; padding: 10px; border: 1px solid #ccc; border-radius: 4px;">
            <p style="color: gray; font-size: 0.8em; margin-top: 5px;">Wielkość liter nie ma znaczenia.</p>
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

// Rejestracja w menu
window.customCards = window.customCards || [];
window.customCards.push({
  type: "employee-card",
  name: "Karta Pracownika (Auto)",
  preview: true,
  description: "Automatycznie wykrywa sensory pracownika"
});