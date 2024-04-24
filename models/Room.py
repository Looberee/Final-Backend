from database import db
import base64
import logging
from sqlalchemy.event import listens_for
import random
import string
from sqlalchemy.orm import relationship
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Room(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    host_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    creation_time = db.Column(db.DateTime, default=db.func.current_timestamp())
    encode_id = db.Column(db.String(255), nullable=True)
    room_member = relationship('RoomMember', back_populates='room')
    
    def encode_p_id(self):
        random_string = ''.join(random.choices(string.ascii_letters + string.digits, k=5))
        id_with_suffix = f"{random_string}{self.id}room"
        return base64.b64encode(id_with_suffix.encode()).decode()

    @staticmethod
    def decode_id(encoded_id):
        decoded_id_with_suffix = base64.b64decode(encoded_id).decode()
        return int(decoded_id_with_suffix.replace('room', ''))
    
    def __init__(self, name, host_id):
        self.name = name
        self.host_id = host_id
        self.encode_id = self.encode_p_id()
        
        
@listens_for(Room, 'after_insert')
def generate_encoded_id(mapper, connection, target):
    try:
        encode_id = target.encode_p_id()
        logger.info(f"Encoded ID generated for Room '{target.name}': {encode_id}")
        connection.execute(
            Room.__table__.update().
            where(Room.id == target.id).
            values(encode_id=encode_id)
        )
    except Exception as e:
        logger.error(f"Error generating encoded ID for Room '{target.name}': {str(e)}")