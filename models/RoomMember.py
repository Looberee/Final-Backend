from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import db  # Assuming db is your SQLAlchemy instance
from .Room import Room

class RoomMember(db.Model):
    __tablename__ = 'room_member'

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('user.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    join_time = Column(DateTime, nullable=False)
    

    # Define relationships
    user = relationship('User', back_populates='room_member')
    room = relationship('Room', back_populates='room_member')

    def __init__(self, user_id, room_id, join_time):
        self.user_id = user_id
        self.room_id = room_id
        self.join_time = join_time