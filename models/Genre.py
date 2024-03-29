from database import db
import base64
from sqlalchemy.event import listens_for
import random
import string
import logging


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Genre(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    genre_name = db.Column(db.String(255), unique=True, nullable=False)
    cloudinary_image_url = db.Column(db.String(255))
    encode_id = db.Column(db.String(100), unique=True, nullable=True)
    
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}genre"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        return int(decoded_id_with_suffix.replace('genre', ''))

    def __init__(self, genre_name, cloudinary_image_url=None):
        self.genre_name = genre_name
        self.cloudinary_image_url = cloudinary_image_url
        
@listens_for(Genre, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for Genre '{target.genre_name}': {encode_id}")
        connection.execute(
            Genre.__table__.update().
            where(Genre.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for Genre '{target.name}': {str(e)}")