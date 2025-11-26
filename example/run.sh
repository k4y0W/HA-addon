#!/usr/bin/with-contenv bashio

echo "Sprawdzam i pobieram wymagane karty..."

mkdir -p /config/www/community_cards

download_card() {
    URL=$1
    FILE=$2
    if [ ! -f "$FILE" ]; then
        echo "Pobieram: $FILE"
        wget -q -O "$FILE" "$URL"
    else
        echo "Istnieje: $FILE"
    fi
}

# 1. Auto-Entities
download_card "https://github.com/thomasloven/lovelace-auto-entities/releases/latest/download/auto-entities.js" "/config/www/community_cards/auto-entities.js"

# 2. ApexCharts Card
download_card "https://github.com/RomRider/apexcharts-card/releases/latest/download/apexcharts-card.js" "/config/www/community_cards/apexcharts-card.js"

# 3. Template Entity Row
download_card "https://github.com/thomasloven/lovelace-template-entity-row/releases/latest/download/template-entity-row.js" "/config/www/community_cards/template-entity-row.js"

# 4. Nasz addon
cp /employee-card.js /config/www/employee-card.js

echo "Uruchamiam logikę..."
python3 /employee_logic.py & 

echo "Uruchamiam serwer WWW..."
exec python3 -m gunicorn web_server:app --bind 0.0.0.0:8099 --workers 1 --log-level info