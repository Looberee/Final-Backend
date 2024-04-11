from database import db
from datetime import datetime

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    transaction_id = db.Column(db.String(120), unique=True, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(3), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    email = db.Column(db.String(120), nullable=False)  # New field
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    
    def __init__(self, user_id, transaction_id, amount, currency, status, email):
        self.user_id = user_id
        self.transaction_id = transaction_id
        self.amount = amount
        self.currency = currency
        self.status = status
        self.email = email 