#!/usr/bin/with-contenv bashio

echo "🔧 Przygotowanie środowiska..."

# 1. Tworzymy folder na zewnętrzne karty (żeby nie robić bałaganu w głównym katalogu)
mkdir -p /config/www/community_cards

# Funkcja pobierająca plik (jeśli go nie ma lub wymuszasz aktualizację)
download_card() {
    URL=$1
    DEST=$2
    echo "📥 Pobieram: $DEST"
    # Używamy wget. || true sprawia, że jeśli nie ma neta, dodatek się nie wywali.
    wget -q --no-check-certificate -O "$DEST" "$URL" || echo "⚠️ Błąd pobierania (brak internetu?): $URL"
}

# 2. Pobieramy wymagane karty HACS (bezpośrednio z ich repozytoriów)
# ApexCharts Card (do wykresów)
download_card "https://github.com/RomRider/apexcharts-card/releases/latest/download/apexcharts-card.js" "/config/www/community_cards/apexcharts-card.js"

# Auto-Entities (do automatycznych list)
download_card "https://github.com/thomasloven/lovelace-auto-entities/releases/latest/download/auto-entities.js" "/config/www/community_cards/auto-entities.js"

# 3. Kopiujemy TWOJĄ kartę (z wnętrza kontenera do HA)
if [ -f "/employee-card.js" ]; then
    cp /employee-card.js /config/www/employee-card.js
    echo "✅ Skopiowano employee-card.js"
else
    echo "⚠️ Nie znaleziono /employee-card.js w kontenerze!"
fi

echo "🚀 Uruchamiam logikę..."
python3 /employee_logic.py & 

echo "🚀 Uruchamiam serwer WWW..."
exec python3 -m gunicorn web_server:app --bind 0.0.0.0:8099 --workers 1 --log-level info