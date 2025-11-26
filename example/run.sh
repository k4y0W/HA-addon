#!/usr/bin/with-contenv bashio
echo "Instaluje karte Lovelace..."
mkdir -p /config/www
cp /employee-card.js /config/www/employee-card.js
echo "Uruchamiam logikę pracownika..."
python3 /employee_logic.py & 
echo "Uruchamiam Gunicorn..."
exec python3 -m gunicorn web_server:app --bind 0.0.0.0:8099 --workers 1 --log-level info