from database import db
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

class Admin(UserMixin, db.Model):
    __tablename__ = 'admin'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(25))
    email = db.Column(db.String(25), unique=True, nullable=False)
    username = db.Column(db.String(25), unique=True, nullable=False)
    password = db.Column(db.String(256), nullable=False)
    date = db.Column(db.DateTime, nullable=True)
    company = db.Column(db.String(25), default="N/A", nullable=False)
    job = db.Column(db.String(25), default="N/A", nullable=False)
    country = db.Column(db.String(25), default="N/A", nullable=False)
    address = db.Column(db.String(125), default="N/A", nullable=False)
    phone = db.Column(db.String(25), default="N/A", nullable=False)
    priority = db.Column(db.Boolean, default=False)

    def __init__(self, name, email, username, password, datetime, priority):
        db.Model.__init__(self)
        self.name = name
        self.email = email
        self.username = username
        self.password = generate_password_hash(password)  # Hash the password
        self.date = datetime
        self.priority = priority
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'email': self.email,
            'username': self.username,
            'date': self.date,
            'company': self.company,
            'job': self.job,
            'country': self.country,
            'address': self.address,
            'phone': self.phone,
            'priority': self.priority
        }
    
    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)