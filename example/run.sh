#!/usr/bin/with-contenv bashio

echo "🔧 Sprawdzam i pobieram wymagane karty..."

# Tworzymy folder na karty zewnętrzne
mkdir -p /config/www/community_cards

# Funkcja pobierająca (odporna na błędy)
download_card() {
    URL=$1
    FILE=$2
    if [ ! -f "$FILE" ]; then
        echo "📥 Pobieram: $FILE"
        # Dodajemy '|| true' żeby błąd wget nie zatrzymał skryptu
        wget -q --no-check-certificate -O "$FILE" "$URL" || echo "⚠️ Błąd pobierania: $URL"
    else
        echo "✅ Istnieje: $FILE"
    fi
}

# Pobieramy karty (ignorując błędy)
download_card "https://github.com/thomasloven/lovelace-auto-entities/releases/latest/download/auto-entities.js" "/config/www/community_cards/auto-entities.js"
download_card "https://github.com/RomRider/apexcharts-card/releases/latest/download/apexcharts-card.js" "/config/www/community_cards/apexcharts-card.js"
download_card "https://raw.githubusercontent.com/thomasloven/lovelace-template-entity-row/master/dist/template-entity-row.js" "/config/www/community_cards/template-entity-row.js"

# Kopiujemy Twoją kartę
if [ -f "/employee-card.js" ]; then
    cp /employee-card.js /config/www/employee-card.js
    echo "✅ Skopiowano employee-card.js"
else
    echo "⚠️ Nie znaleziono /employee-card.js w kontenerze!"
fi

echo "🚀 Uruchamiam logikę..."
# Uruchamiamy logikę w tle, ignorując błędy startowe
python3 /employee_logic.py & 

echo "🚀 Uruchamiam serwer WWW..."
# To jest główny proces, który trzyma kontener przy życiu
exec python3 -m gunicorn web_server:app --bind 0.0.0.0:8099 --workers 1 --log-level info