from models.Track import Track
from models.Room import Room

from sqlalchemy import Column, Integer, ForeignKey, DateTime
from sqlalchemy.orm import relationship
from database import db  # Assuming db is your SQLAlchemy instance

class RoomTrack(db.Model):
    __tablename__ = 'room_track'

    id = Column(Integer, primary_key=True)
    track_id = Column(Integer, ForeignKey('track.id'), nullable=False)
    room_id = Column(Integer, ForeignKey('room.id'), nullable=False)
    added_time = Column(DateTime, nullable=False)


    # Define relationships
    track = db.relationship('Track', back_populates='room_track')
    room = db.relationship('Room', back_populates='room_track')
    
    def __init__(self, track_id, room_id, added_time):
        self.track_id = track_id
        self.room_id = room_id
        self.added_time = added_time