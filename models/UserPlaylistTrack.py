from database import db
import base64
from sqlalchemy.event import listens_for
import random
import string
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Association Table for UserPlaylists and Tracks
user_playlist_track_association = db.Table(
    'user_playlist_track_association',
    db.Column('user_playlist_id', db.Integer, db.ForeignKey('user_playlist.id')),
    db.Column('track_id', db.Integer, db.ForeignKey('track.id')),
    extend_existing=True  # Add this parameter to extend the existing table definition
)

class UserPlaylistTrack(db.Model):
    __tablename__ = 'user_playlist_track'

    id = db.Column(db.Integer, primary_key=True)
    user_playlist_id = db.Column(db.Integer, db.ForeignKey('user_playlist.id'))
    user_playlist = db.relationship('UserPlaylist', back_populates='tracks')
    track_id = db.Column(db.Integer, db.ForeignKey('track.id'))  # Assuming track_id is an integer foreign key
    track = db.relationship('Track', backref='user_playlist_tracks')
    encode_id = db.Column(db.String(100), unique=True, nullable=True)
    
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}userplaylisttrack"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        split_id = decoded_id_with_suffix.split("userplaylisttrack")
        if len(split_id) > 1:
            id_with_random_string = split_id[1]
            id_without_random_string = id_with_random_string[5:]
            return int(id_without_random_string)
        else:
            return None

    def __repr__(self):
        return f'<UserPlaylistTrack {self.id}>'

    def __init__(self, user_playlist_id, track_id):
        self.user_playlist_id = user_playlist_id
        self.track_id = track_id
        self.encode_id = self.encode_p_id()

@listens_for(UserPlaylistTrack, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for UserPlaylist '{target.id}': {encode_id}")
        connection.execute(
            UserPlaylistTrack.__table__.update().
            where(UserPlaylistTrack.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for UserPlaylist '{target.id}': {str(e)}")
