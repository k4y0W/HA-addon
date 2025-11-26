```mermaid
graph TD
    %% Style definitions
    classDef physical fill:#e1f5fe,stroke:#01579b,color:#01579b;
    classDef addon fill:#fff3e0,stroke:#e65100,color:#e65100;
    classDef virtual fill:#e8f5e9,stroke:#1b5e20,color:#1b5e20;
    classDef user fill:#f3e5f5,stroke:#4a148c,color:#4a148c;

    subgraph HA_CORE [Home Assistant Core / Rejestr Encji]
        Entity_Source1[("🔌 Encja Źródłowa 1\n(np. sensor.gniazdko_moc)")]:::physical
        Entity_Source2[("🏃 Encja Źródłowa 2\n(np. binary_sensor.ruch)")]:::physical
        
        Entity_Virtual_Status(["👤 Wirtualny Sensor: STATUS\n(np. sensor.monika_status)"]) :::virtual
        Entity_Virtual_Time(["⏱️ Wirtualny Sensor: CZAS\n(np. sensor.monika_czas_pracy)"]) :::virtual
        Entity_Virtual_Clone(["👁️ Wirtualny Sensor: KLON\n(np. sensor.monika_moc)"]) :::virtual
    end

    subgraph ADDON [Add-on: Employee Manager]
        Employee_Config[["📄 Konfiguracja Pracownika\n(employees.json)"]]:::user
        Logic_Engine{{"⚙️ Silnik Logiczny\n(Python Script)"}}:::addon
    end

    %% Relacje
    Entity_Source1 -- "Odczyt stanu (np. 160W)" --> Logic_Engine
    Entity_Source2 -- "Odczyt stanu (np. 'on')" --> Logic_Engine
    
    Employee_Config -- "Definiuje mapowanie:\nMonika = [Źródło1, Źródło2]" --> Logic_Engine
    
    Logic_Engine -- "Przetwarzanie reguł\n(np. IF Moc > 20W AND Ruch = ON)" --> Logic_Engine
    
    Logic_Engine -- "Tworzy / Aktualizuje\n(Stan: Pracuje)" --> Entity_Virtual_Status
    Logic_Engine -- "Tworzy / Aktualizuje\n(Stan: 125 min)" --> Entity_Virtual_Time
    Logic_Engine -- "Kopiuje wartość 1:1\n(Stan: 160W)" --> Entity_Virtual_Clone
```