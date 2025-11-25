import logging
from flask import Flask, redirect

_LOGGER = logging.getLogger(__name__)

# Standardowy port Ingress
PORT = 8099 

# Tworzymy aplikację Flask
app = Flask(__name__)

@app.route('/')
def index():
    # Po prostu zwracamy komunikat, że dodatek działa
    return "<h1>Employee Manager: Dodatek działa poprawnie. Logika uruchomiona w tle.</h1>"

def start_server():
    _LOGGER.info("Starting web server on port 8099")
    try:
        # Gunicorn jest bardziej wydajny niż wbudowany serwer Flaska
        from gunicorn.app.base import BaseApplication

        class FlaskServer(BaseApplication):
            def __init__(self, app, options=None):
                self.options = options or {}
                self.application = app
                super().__init__()

            def load_config(self):
                for key, value in self.options.items():
                    self.cfg.set(key.lower(), value)

            def load(self):
                return self.application

        options = {
            'bind': f'0.0.0.0:{PORT}',
            'workers': 1,
            'accesslog': '-',
            'errorlog': '-',
            'loglevel': 'info',
        }
        FlaskServer(app, options).run()
    except Exception as e:
        _LOGGER.error(f"Failed to start web server: {e}")

if __name__ == '__main__':
    start_server()