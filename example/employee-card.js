class EmployeeCard extends HTMLElement {
  // 1. Konfiguracja: Użytkownik podaje tylko imię
  setConfig(config) {
    if (!config.name) {
      throw new Error('Musisz podać imię pracownika (name)!');
    }
    this.config = config;
  }

  // 2. Główna pętla: Uruchamia się przy każdej zmianie w Home Assistant
  set hass(hass) {
    const name = this.config.name;
    // Konwertujemy "Jan Kowalski" na "jan_kowalski" (tak jak Twój Python)
    const entityIdBase = name.toLowerCase().replace(/ /g, "_")
                             .replace(/ą/g, 'a').replace(/ć/g, 'c').replace(/ę/g, 'e')
                             .replace(/ł/g, 'l').replace(/ń/g, 'n').replace(/ó/g, 'o')
                             .replace(/ś/g, 's').replace(/ź/g, 'z').replace(/ż/g, 'z');

    const statusEntity = hass.states[`sensor.${entityIdBase}_status`];
    const timeEntity = hass.states[`sensor.${entityIdBase}_czas_pracy`];

    // Rysowanie karty (tylko raz)
    if (!this.content) {
      this.innerHTML = `
        <style>
          ha-card {
            padding: 16px;
            display: flex;
            align-items: center;
            cursor: pointer;
            transition: all 0.2s ease-in-out;
          }
          ha-card:hover {
            box-shadow: 0 4px 8px rgba(0,0,0,0.15);
          }
          .icon-container {
            width: 45px; 
            height: 45px; 
            border-radius: 50%; 
            display: flex; 
            align-items: center; 
            justify-content: center; 
            margin-right: 15px;
            background: #eee;
            color: #555;
          }
          /* Kolory statusów */
          .status-working { background: rgba(76, 175, 80, 0.2); color: #2E7D32; } /* Zielony */
          .status-idle { background: rgba(255, 193, 7, 0.2); color: #F57F17; }    /* Żółty */
          .status-absent { background: rgba(244, 67, 54, 0.2); color: #C62828; }  /* Czerwony */

          .info { flex: 1; }
          .name { font-weight: 600; font-size: 1.1rem; }
          .status-text { font-size: 0.85rem; opacity: 0.8; }
          
          .stats { text-align: right; }
          .time-val { font-size: 1.2rem; font-weight: bold; }
          .time-unit { font-size: 0.7rem; opacity: 0.7; }
        </style>
        <ha-card>
          <div class="icon-container" id="icon">
            <ha-icon icon="mdi:account"></ha-icon>
          </div>
          <div class="info">
            <div class="name">${name}</div>
            <div class="status-text" id="status">Ładowanie...</div>
          </div>
          <div class="stats">
            <div class="time-val" id="time">--</div>
            <div class="time-unit">MINUT DZIŚ</div>
          </div>
        </ha-card>
      `;
      this.content = this.querySelector('ha-card');
    }

    // Aktualizacja danych na żywo
    if (statusEntity) {
      const state = statusEntity.state;
      const iconDiv = this.querySelector('#icon');
      const statusDiv = this.querySelector('#status');

      statusDiv.innerText = state;

      // Reset klas i ustawienie nowej
      iconDiv.className = 'icon-container';
      if (state === 'Pracuje') {
        iconDiv.classList.add('status-working');
        this.querySelector('ha-icon').setAttribute('icon', 'mdi:laptop');
      } else if (state === 'Obecny (Idle)') {
        iconDiv.classList.add('status-idle');
        this.querySelector('ha-icon').setAttribute('icon', 'mdi:coffee');
      } else {
        iconDiv.classList.add('status-absent');
        this.querySelector('ha-icon').setAttribute('icon', 'mdi:account-off');
      }
    }

    if (timeEntity) {
      this.querySelector('#time').innerText = timeEntity.state;
    }
  }

  // Definicja wielkości karty (dla Lovelace)
  getCardSize() {
    return 1;
  }
}

// Rejestracja karty w Home Assistant
customElements.define('employee-card', EmployeeCard);

// Dodanie do listy "Dodaj kartę" (To sprawia, że jest user-friendly!)
window.customCards = window.customCards || [];
window.customCards.push({
  type: "employee-card",
  name: "Karta Pracownika (Employee Manager)",
  preview: true,
  description: "Dedykowana karta do wyświetlania statusu pracownika"
});