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
    db.Column('track_id', db.Integer, db.ForeignKey('track.id'))
)

class UserPlaylist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    encode_id = db.Column(db.String(100), unique=True, nullable=True)
    user = db.relationship('User', backref=db.backref('playlists', lazy=True))

    # Define many-to-many relationship with Track
    tracks = db.relationship('UserPlaylistTrack', back_populates='user_playlist')
    
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}userplaylist"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        split_id = decoded_id_with_suffix.split("userplaylist")
        if len(split_id) > 1:
            id_with_random_string = split_id[1]
            id_without_random_string = id_with_random_string[5:]
            return int(id_without_random_string)
        else:
            return None

    def __init__(self, name, user_id):
        self.name = name
        self.user_id = user_id
        self.encode_id = self.encode_p_id()

@listens_for(UserPlaylist, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for UserPlaylist '{target.name}': {encode_id}")
        connection.execute(
            UserPlaylist.__table__.update().
            where(UserPlaylist.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for UserPlaylist '{target.name}': {str(e)}")
