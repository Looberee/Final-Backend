from database import db
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
import base64
import logging
from sqlalchemy.event import listens_for
import random
import string
from sqlalchemy.orm import relationship

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

from .RoomMember import RoomMember

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='regular')
    encode_id = db.Column(db.String(100), nullable=True, unique=True)
    room_member = relationship('RoomMember', back_populates='user')

    def __init__(self, username, email, password):
        self.username = username
        self.email = email
        self.set_password(password)
        
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}user"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        # Split the decoded string by the random string separator
        split_id = decoded_id_with_suffix.split("userplaylisttrack")
        if len(split_id) > 1:
            id_with_random_string = split_id[1]  # The second part after the separator is the ID
            # Remove the random string from the ID
            id_without_random_string = id_with_random_string[5:]  # Remove the first 5 characters
            return int(id_without_random_string)  # Convert the ID to an integer
        else:
            return None  # Handle error or return None if the format is incorrect

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

@listens_for(User, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for User {target.username}: {encode_id}")
        connection.execute(
            User.__table__.update().
            where(User.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for User {target.username}: {str(e)}")

