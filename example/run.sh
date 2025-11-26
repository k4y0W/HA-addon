#!/usr/bin/with-contenv bashio

echo "🔧 Przygotowanie środowiska..."

mkdir -p /config/www/community_cards

download_card() {
    URL=$1
    DEST=$2
    echo "📥 Pobieram: $DEST"
    # Flaga -L pozwala na podążanie za przekierowaniami
    wget -q -L --no-check-certificate -O "$DEST" "$URL" || echo "⚠️ Błąd pobierania: $URL"
}

# Używamy pewnych linków
download_card "https://raw.githubusercontent.com/thomasloven/lovelace-auto-entities/master/auto-entities.js" "/config/www/community_cards/auto-entities.js"
download_card "https://raw.githubusercontent.com/RomRider/apexcharts-card/master/dist/apexcharts-card.js" "/config/www/community_cards/apexcharts-card.js"
download_card "https://raw.githubusercontent.com/thomasloven/lovelace-template-entity-row/master/dist/template-entity-row.js" "/config/www/community_cards/template-entity-row.js"

if [ -f "/employee-card.js" ]; then
    cp /employee-card.js /config/www/employee-card.js
    echo "✅ Skopiowano employee-card.js"
else
    echo "⚠️ Brak /employee-card.js"
fi

echo "🚀 Uruchamiam logikę..."
python3 /employee_logic.py & 

echo "🚀 Uruchamiam serwer WWW..."
exec python3 -m gunicorn web_server:app --bind 0.0.0.0:8099 --workers 1 --log-level info