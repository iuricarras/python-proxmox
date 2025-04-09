from flask import Flask
from flask_cors import CORS
from proxmoxer import ProxmoxAPI

proxmox = None

def create_app():
    app = Flask(__name__)
    CORS(app)  

    global proxmox

    

    from .main import main as main_blueprint
    app.register_blueprint(main_blueprint)

    return app