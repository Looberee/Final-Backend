from database import db
import base64
import logging
from sqlalchemy.event import listens_for
import random
import string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

user_preference_track = db.Table('user_preference_track',
    db.Column('user_preference_id', db.Integer, db.ForeignKey('user_preference.id'), primary_key=True),
    db.Column('track_id', db.Integer, db.ForeignKey('track.id'), primary_key=True)
)

# Association table for the many-to-many relationship between UserPreference and Artist
user_preference_artist = db.Table('user_preference_artist',
    db.Column('user_preference_id', db.Integer, db.ForeignKey('user_preference.id'), primary_key=True),
    db.Column('artist_id', db.Integer, db.ForeignKey('artist.id'), primary_key=True)
)

class UserPreference(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    favorite_tracks = db.relationship('Track', secondary=user_preference_track, backref='user_preferences')
    favorite_artists = db.relationship('Artist', secondary=user_preference_artist, backref='user_preferences')
    encode_id = db.Column(db.String(100), unique=True, nullable=True)
    
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}userpreference"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        return int(decoded_id_with_suffix.replace('userpreference', ''))

    def __init__(self, user_id):
        self.user_id = user_id
        self.encode_id = self.encode_p_id()
        logger.info(f"Encoded ID generated for UserPreference '{self.id}': {self.encode_id}")

@listens_for(UserPreference, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for UserPreference '{target.id}': {encode_id}")
        connection.execute(
            UserPreference.__table__.update().
            where(UserPreference.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for UserPreference '{target.id}': {str(e)}")
