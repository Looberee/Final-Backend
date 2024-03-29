from database import db
from datetime import datetime
import base64
import logging
from sqlalchemy.event import listens_for
import random
import string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RecentTrack(db.Model):
    __tablename__ = 'recent_track'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'))  # Assuming track_id is an integer foreign key
    track = db.relationship('Track', backref='user_playlist_track')
    played_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    encode_id = db.Column(db.String(100), unique=True, nullable=True)
    spotify_id = db.Column(db.String(100), nullable=False)
    
    
    def __init__(self, user_id, track_id, played_at, spotify_id):
        self.user_id = user_id
        self.track_id = track_id
        self.played_at = played_at
        self.encode_id = self.encode_p_id()
        self.spotify_id = spotify_id
        
        
    
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}recenttrack"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        return int(decoded_id_with_suffix.replace('recenttrack', ''))

    def __repr__(self):
        return f"<RecentTrack user_id={self.user_id}, track_id={self.track_id}, played_at={self.played_at}>"

@listens_for(RecentTrack, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for RecentTrack: {encode_id}")
        connection.execute(
            RecentTrack.__table__.update().
            where(RecentTrack.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for RecentTrack: {str(e)}")
