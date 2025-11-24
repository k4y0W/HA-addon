#!/usr/bin/with-contenv bashio

echo "Uruchamiam Employee Managera..."

python3 /employee_logic.py &

while true; do 
    sleep 30
done