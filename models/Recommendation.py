from database import db
from datetime import datetime
import base64
import logging
from sqlalchemy.event import listens_for
import random
import string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Recommendation(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'), nullable=False)
    source = db.Column(db.String(100))  # Source of the recommendation (e.g., algorithm name, user's friend)
    recommendation_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    name = db.Column(db.String(100))  # Name or title of the recommendation list
    encode_id = db.Column(db.String(100), unique=True, nullable=True)
    
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}recommendation"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        return int(decoded_id_with_suffix.replace('recommendation', ''))

    # Define relationships
    user = db.relationship('User', backref='recommendations')
    track = db.relationship('Track', backref='recommendations')

    def __init__(self, user_id, track_id, source, name):
        self.user_id = user_id
        self.track_id = track_id
        self.source = source
        self.name = name
        self.encode_id = self.encode_p_id()

@listens_for(Recommendation, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for Recommendation: {encode_id}")
        connection.execute(
            Recommendation.__table__.update().
            where(Recommendation.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for Recommendation: {str(e)}")
