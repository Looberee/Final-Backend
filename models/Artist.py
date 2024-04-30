from database import db
import base64
import logging
from sqlalchemy.event import listens_for
import random
import string

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Artist(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    spotify_id = db.Column(db.String(255))
    name = db.Column(db.String(255), nullable=False)
    cloudinary_artist_image_url = db.Column(db.String(255))
    genres = db.Column(db.String(100))
    followers = db.Column(db.Integer)
    encode_id = db.Column(db.String(100), unique=True, nullable=True)
    
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}artist"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        return int(decoded_id_with_suffix.replace('artist', ''))

    def __init__(self, spotify_id, name, cloudinary_artist_image_url=None, genres=None, followers=0):
        self.spotify_id = spotify_id
        self.name = name
        self.cloudinary_artist_image_url = cloudinary_artist_image_url
        self.genres = genres
        self.followers = followers
        self.encode_id = self.encode_p_id()
        logger.info(f"Encoded ID generated for Artist '{self.name}': {self.encode_id}")
        
    def to_dict(self):
        return {
            'id': self.id,
            'spotify_id': self.spotify_id,
            'name': self.name,
            'cloudinary_artist_image_url': self.cloudinary_artist_image_url,
            'genres': self.genres,
            'followers': self.followers,
            'encode_id': self.encode_id
        }

@listens_for(Artist, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for Artist '{target.name}': {encode_id}")
        connection.execute(
            Artist.__table__.update().
            where(Artist.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for Artist '{target.name}': {str(e)}")
