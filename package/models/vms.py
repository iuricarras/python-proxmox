from package import db
from dataclasses import dataclass

@dataclass
class VM(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name:str = db.Column(db.String(50), unique=True)