from database import db
from datetime import datetime
from flask_jwt_extended import get_jti, decode_token

class RefreshToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    jti = db.Column(db.String(36), nullable=False)  # JTI is the unique identifier for the token
    issued_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    expires_in = db.Column(db.DateTime, nullable=False)
    revoked = db.Column(db.Boolean, nullable=False, default=False)

    user = db.relationship('User', backref='refresh_tokens')

    def __init__(self, jti=None, user_id=None, issued_at=None, expires_in=None, revoked=False):
        self.jti = jti
        self.user_id = user_id
        self.issued_at = issued_at or datetime.utcnow()
        self.expires_in = expires_in
        self.revoked = revoked

# Function to generate and store refresh token in the database
def insert_refresh_token(refresh_token, user_id):
    jti = get_jti(refresh_token)
    expires_in = datetime.fromtimestamp(decode_token(refresh_token)['exp'])
    token_record = RefreshToken(jti=jti, user_id=user_id, expires_in=expires_in)
    db.session.add(token_record)
    db.session.commit()
    return refresh_token

# Function to check if refresh token exists in the database
def is_valid_refresh_token(refresh_token):
    return RefreshToken.query.filter_by(token=refresh_token).first() is not None

def get_refresh_token(user_id):
    token = RefreshToken.query.filter_by(user_id=user_id, revoked=False).first()
    if token:
        return token.jti
    else:
        return None