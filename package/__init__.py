from flask import Flask
from flask_cors import CORS
from proxmoxer import ProxmoxAPI
from flask_sqlalchemy import SQLAlchemy
import os

proxmox = None

db = SQLAlchemy()

from .models.vms import VM


app = Flask(__name__)
CORS(app)  


app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///db.sqlite'

db.init_app(app)

with app.app_context():
    if not os.path.exists('db.sqlite'):
        db.create_all()

print("Database created")
from .flaskapi import main as main_blueprint
print("Registering main blueprint")
app.register_blueprint(main_blueprint)
