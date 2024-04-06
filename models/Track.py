from database import db
import base64
import logging
from sqlalchemy.event import listens_for
import random
import string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Track(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255), unique=True, nullable=False)
    name = db.Column(db.String(255))
    album_id = db.Column(db.String(255))
    artists = db.Column(db.String(255))  # Store as comma-separated string
    duration_ms = db.Column(db.Integer)
    popularity = db.Column(db.Integer)
    preview_url = db.Column(db.String(255))
    release_date = db.Column(db.String(255))
    album_name = db.Column(db.String(255))
    album_release_date = db.Column(db.String(255))
    cloudinary_img_url = db.Column(db.String(255))
    encode_id = db.Column(db.String(100), unique=True, nullable=True)
    track_genres = db.Column(db.String(255), nullable=True)  # Set nullable to True

    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}track"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        return int(decoded_id_with_suffix.replace('track', ''))

    def __init__(self, spotify_id, name, album_id , artists, duration_ms, popularity, preview_url, release_date, album_name, album_release_date, cloudinary_img_url, track_genres):
        self.spotify_id = spotify_id
        self.name = name
        self.album_id = album_id
        self.artists = artists
        self.duration_ms = duration_ms
        self.popularity = popularity
        self.preview_url = preview_url
        self.release_date = release_date
        self.album_name = album_name
        self.album_release_date = album_release_date
        self.cloudinary_img_url = cloudinary_img_url
        self.encode_id = self.encode_p_id()
        self.track_genres = track_genres
        logger.info(f"Encoded ID generated for Track '{self.name}': {self.encode_id}")
        
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'artists': self.artists,
            'spotify_image_url' : self.cloudinary_img_url,
            'spotify_id' : self.spotify_id,
            'duration' : self.duration_ms
        }

@listens_for(Track, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for Track '{target.name}': {encode_id}")
        connection.execute(
            Track.__table__.update().
            where(Track.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for Track '{target.name}': {str(e)}")
