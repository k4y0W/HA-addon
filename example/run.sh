#!/usr/bin/with-contenv bashio

echo "Uruchamiam logikę pracownika (Backend)..."
python3 /employee_logic.py & 

echo "Uruchamiam Gunicorn (Frontend)..."
exec python3 -m gunicorn web_server:app --bind 0.0.0.0:8099 --workers 1 --log-level info