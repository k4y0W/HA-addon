class EmployeeCard extends HTMLElement {
  // --- LOGIKA KARTY (To co już miałeś) ---
  setConfig(config) {
    if (!config.name) {
      throw new Error('Wpisz imię pracownika w edytorze!');
    }
    this.config = config;
  }

  set hass(hass) {
    const name = this.config.name;
    // Zamiana polskich znaków i spacji na ID
    const entityIdBase = name.toLowerCase().replace(/ /g, "_")
                             .replace(/ą/g, 'a').replace(/ć/g, 'c').replace(/ę/g, 'e')
                             .replace(/ł/g, 'l').replace(/ń/g, 'n').replace(/ó/g, 'o')
                             .replace(/ś/g, 's').replace(/ź/g, 'z').replace(/ż/g, 'z');

    const statusEntity = hass.states[`sensor.${entityIdBase}_status`];
    const timeEntity = hass.states[`sensor.${entityIdBase}_czas_pracy`];

    if (!this.content) {
      this.innerHTML = `
        <style>
          ha-card { padding: 16px; display: flex; align-items: center; cursor: pointer; transition: all 0.2s; }
          ha-card:hover { box-shadow: 0 4px 8px rgba(0,0,0,0.15); }
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
        </style>
        <ha-card>
          <div class="icon-container" id="icon"><ha-icon icon="mdi:account"></ha-icon></div>
          <div class="info"><div class="name"></div><div class="status-text" id="status"></div></div>
          <div class="stats"><div class="time-val" id="time">--</div><div class="time-unit">MINUT DZIŚ</div></div>
        </ha-card>
      `;
      this.content = this.querySelector('ha-card');
      this.querySelector('.name').innerText = name;
    }

    if (statusEntity) {
      const state = statusEntity.state;
      const iconDiv = this.querySelector('#icon');
      const statusDiv = this.querySelector('#status');
      statusDiv.innerText = state;
      
      iconDiv.className = 'icon-container';
      let iconName = 'mdi:account-off';
      if (state === 'Pracuje') { iconDiv.classList.add('status-working'); iconName = 'mdi:laptop'; }
      else if (state === 'Obecny (Idle)') { iconDiv.classList.add('status-idle'); iconName = 'mdi:coffee'; }
      else { iconDiv.classList.add('status-absent'); }
      
      this.querySelector('ha-icon').setAttribute('icon', iconName);
    }
    if (timeEntity) {
      this.querySelector('#time').innerText = timeEntity.state;
    }
  }

  getCardSize() { return 1; }

  // --- KONFIGURACJA EDYTORA WIZUALNEGO ---
  static getStubConfig() {
    return { name: "Marek" }; // Domyślna wartość po dodaniu karty
  }

  static getConfigElement() {
    return document.createElement("employee-card-editor");
  }
}

// --- KLASA EDYTORA (FORMULARZ) ---
class EmployeeCardEditor extends HTMLElement {
  setConfig(config) {
    this._config = config;
    this.render();
  }

  render() {
    if (!this.innerHTML) {
      this.innerHTML = `
        <div class="card-config">
          <div class="input-container" style="padding: 20px 0;">
            <label style="display:block; margin-bottom: 8px;">Imię Pracownika (z Konfiguracji)</label>
            <input type="text" id="name-input" style="width: 100%; padding: 8px; border: 1px solid #ccc; border-radius: 4px;">
            <p style="color: gray; font-size: 0.8em; margin-top: 5px;">Wpisz imię dokładnie tak, jak w panelu Employee Manager.</p>
          </div>
        </div>
      `;
      
      // Obsługa zdarzenia wpisywania
      this.querySelector('#name-input').addEventListener('input', (e) => {
        this._valueChanged(e.target.value);
      });
    }
    this.querySelector('#name-input').value = this._config.name || '';
  }

  _valueChanged(newVal) {
    // Wysyłamy zdarzenie do Home Assistant, że konfiguracja się zmieniła
    const event = new CustomEvent("config-changed", {
      detail: { config: { ...this._config, name: newVal } },
      bubbles: true,
      composed: true,
    });
    this.dispatchEvent(event);
  }
}

// Rejestracja obu klas
customElements.define('employee-card-editor', EmployeeCardEditor);
customElements.define('employee-card', EmployeeCard);

// Dodanie do menu "Dodaj kartę"
window.customCards = window.customCards || [];
window.customCards.push({
  type: "employee-card",
  name: "Karta Pracownika (Pro)",
  preview: true,
  description: "Wizualny status pracownika"
});