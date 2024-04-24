from flask import Flask, jsonify, request, redirect
from flask_socketio import SocketIO, join_room, leave_room, send, emit
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity, unset_jwt_cookies, create_refresh_token, set_access_cookies, set_refresh_cookies, verify_jwt_in_request, get_jti, decode_token, get_jwt
from flask_cors import CORS
from flask_redis import FlaskRedis

from discord.ext import commands
import discord  # Add this line
from werkzeug.security import generate_password_hash

from models.Room import Room
from models.User import User
from models.RoomMember import RoomMember
from models.Track import Track
from database import db

from sqlalchemy.orm import joinedload

import spotipy
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
#End importing Spotify API


import cloudinary
from cloudinary import uploader
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
#End importing Cloudinary API

from datetime import datetime
import asyncio
import requests
from urllib.parse import urlencode

import threading
from threading import Thread


app = Flask(__name__)
redis = FlaskRedis(app)
socketio = SocketIO(app, cors_allowed_origins="*")
intents = discord.Intents.default()
intents.voice_states = True

pyppo_bot = commands.Bot(command_prefix='!', intents=intents)
pyppo_token = 'MTIyNjQ5Nzk1NzE3MjM0Njk0MQ.GApILx.O4hBAGwdEn_Q2i3-w09RQPgLYmTRzLLY0ACC8g'

discord_auth = {
    'client_id': '1226497957172346941',
    'client_secret': 'UA6DjTjHQdhllFYoiuVk7RsoE_C19cMR',
    'redirect_uri': 'http://127.0.0.1:5001/callback',
}

client_id = 'f8eb39f738654c94945537405e6ebad1'
client_secret = '27e1646b17d24a32b34cfaf6504a84b1'
redirect_uri = 'http://127.0.0.1:5000/callback'
AUTHORIZE_URL = 'https://accounts.spotify.com/authorize'
TOKEN_URL = 'https://accounts.spotify.com/api/token '

sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope = 'user-library-read user-library-modify user-top-read app-remote-control streaming user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-modify-public user-read-private user-read-email playlist-read-private user-follow-modify'

)




CORS(app, origins=["http://localhost:3000"], supports_credentials=True)

app.secret_key = 'Delta1006'

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:Delta1006@127.0.0.1/pyppo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['CORS_ENABLED'] = True
app.config['JWT_SECRET_KEY'] = app.secret_key
app.config['SECRET_KEY'] = app.secret_key
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False  # Ensure session is not permanent
app.config['REDIS_URL'] = "redis://:Delta1006@localhost:6379/0"
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = True
app.config['JWT_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['JWT_ACCESS_COOKIE_NAME'] = 'access_token_cookie'
app.config['JWT_ACCESS_CSRF_HEADER_NAME'] = 'X-CSRF-TOKEN-ACCESS'
app.config['JWT_ACCESS_CSRF_FIELD_NAME'] = 'csrf_token_access'



socketio.init_app(app)
db.init_app(app)
jwt = JWTManager(app)
jwt.init_app(app)

# -------------------- BOT COMMAND -------------------- #
# @pyppo_bot.command()
# async def pinfo(ctx):
#     await ctx.send("Hello, I am Pyppo! I am the manager of the playback that you will use later. If you want to play something, just type !pplay")
    
# @pyppo_bot.command()
# async def pchat(ctx):
#     await ctx.send("I have no idea what you are talking about")
    
# @pyppo_bot.command()
# async def pplay(ctx, track_url):
#     await ctx.send("Playing " + track_url)
    
# --------------------- REAL-TIME EVENTS --------------------- #
@app.route('/personal/rooms', methods=['GET'])
@jwt_required()
def get_my_rooms():
    host_id = get_jwt_identity()  # Get the host_id from the JWT identity
    my_rooms = Room.query.filter_by(host_id=host_id).all()  # Query for all rooms hosted by this user

    if not my_rooms:
        return jsonify({"error": "No rooms found"}), 404

    # Convert the rooms to a format that can be JSONified
    my_rooms = [{"id": room.id, "name": room.name } for room in my_rooms]

    return jsonify({"my_rooms" : my_rooms}), 200

@app.route('/personal/rooms', methods=['PUT'])
@jwt_required()
def personal_room_edit():
    current_id = get_jwt_identity()
    data = request.get_json()
    room_name = data.get('new_name')
    room_id = data.get('room_id')

    # Find the room in the database
    room = Room.query.filter_by(host_id=current_id, id=room_id).first()
    if room is None:
        return jsonify({'error': 'Room not found'}), 404

    room.name = room_name

    # Save the changes to the database
    db.session.commit()

    # Return a success message
    return jsonify({'message': 'Room updated successfully'}), 200

@app.route('/personal/rooms', methods=['DELETE'])
@jwt_required()
def personal_room_delete():
    current_id = get_jwt_identity()
    data = request.get_json()
    room_id = data.get('room_id')

    # Find the room in the database
    room = Room.query.filter_by(host_id = current_id, id=room_id).first()
    if room is None:
        # If the room doesn't exist, return an error
        return jsonify({'error': 'Room not found'}), 404

    # Delete the room
    db.session.delete(room)

    # Save the changes to the database
    db.session.commit()

    # Return a success message
    return jsonify({'message': 'Room deleted successfully'}), 200


@app.route('/rooms/all', methods=['GET'])
@jwt_required()
def get_all_rooms():
    all_rooms = Room.query.all()  # Query for all rooms

    # Convert the rooms to a format that can be JSONified
    all_rooms = [{"id": room.id, "name": room.name} for room in all_rooms]

    return jsonify({"all_rooms" : all_rooms}), 200

@app.route('/personal/rooms', methods=['POST'])
@jwt_required()
def create_room():
    host_id = get_jwt_identity()  # Get the host_id from the JWT identity

    # Count the number of existing rooms for this user
    room_count = Room.query.filter_by(host_id=host_id).count()

    # Generate the name for the new room
    room_name = f"Room #{room_count + 1}"

    try:
        new_room = Room(name=room_name, host_id=host_id)
    except Exception as e:
        print(e)

    db.session.add(new_room)
    db.session.commit()
    return jsonify({"msg": f"{room_name} created successfully", "room_id": new_room.id})

@socketio.on('join')
@jwt_required()
def on_join(data):
    current_id = get_jwt_identity()
    user = User.query.filter_by(id=current_id).first()
    room_id = data.get('room_id')

    existing_member = RoomMember.query.filter_by(user_id=current_id, room_id=room_id).first()
    if existing_member:
        emit('message', {"msg": "You are already in the room.", "success": False, "user" : "Pyppo"})
        members = get_member(room_id)
        emit('member_list', {'member_list': members}, broadcast=True)
        print("-------------")
        print(user.username + " is already in the room.")
        print("-------------")
    else:
        join_room(room_id)
        new_member = RoomMember(user_id=current_id, room_id=room_id, join_time=datetime.now())
        db.session.add(new_member)
        db.session.commit()
        send({"msg": user.username + " has entered the room.", "success": True, "user" : "Pyppo"}, room=room_id)
        members = get_member(room_id)
        emit('member_list', {'member_list': members}, broadcast=True)
        print("-------------")
        print(user.username + " has entered the room: " + str(room_id))
        print("-------------")


def is_correct_password(room_id, password):
    room = Room.query.filter_by(id=room_id).first()
    if room and room.password == password:
        return True
    else:
        return False

@socketio.on('leave')
@jwt_required()
def on_leave(data):
    current_id = get_jwt_identity()
    user = User.query.filter_by(id=current_id).first()
    room_id = data.get('room_id')
    if room_id is None:
        print("room_id not provided")
        return

    existing_member = RoomMember.query.filter_by(user_id=current_id, room_id=room_id).first()
    if existing_member is None:
        emit('message', {"msg": "You are not in the room.", "success": False})
        members = get_member(room_id)
        emit('member_list', {'member_list': members}, broadcast=True)
        print("-------------")
        print(user.username + " is not in the room.")
        print("-------------")
    else:
        leave_room(room_id)
        db.session.delete(existing_member)
        db.session.commit()
        send({"msg": user.username + " has left the room.", "user" : user.username}, room=room_id)
        members = get_member(room_id)
        emit('member_list', {'member_list': members}, broadcast=True)
        print("-------------")
        print(user.username + " has left the room: " + str(room_id))
        print("-------------")
    
@socketio.on('send_message')
@jwt_required()
def handle_send_message(data):
    msg = data['message']
    room_id = data['room_id']
    current_id = get_jwt_identity()
    user = User.query.filter_by(id=current_id).first()
    # Broadcast the message to all users in the room
    # send({"msg": msg, "success" : "true" ,"user": user.username}, room=room_id)
    emit('message', {"msg" : msg, "room_id" :room_id, "user" : user.username}, broadcast=True)
    print("Message: ", msg);
    
# @socketio.on('command')
# @jwt_required()
# def socket_command(data):
#     msg = data['message']
#     room_id = data['room_id']
#     current_id = get_jwt_identity()
#     user = User.query.filter_by(id=current_id).first()
    
#     if msg.startswith('!pplay'):
#         command, *song = msg.split(' ')
#         song = ' '.join(song)
#         print("Play command in server")
#         print("Track is: ", song)
#         send({"msg": f"{song} has been added to the queue - requested by {user.username} ", "success": True, "user" : "Pyppo"}, room=room_id)
        
        
#     elif msg.startswith('!pchat'):
#         print("Chat command in server")
#     elif msg.startswith('!pinfo'):
#         print("Info command in server")

@jwt_required()
def get_member(room_id):
    members = RoomMember.query.filter_by(room_id=room_id).all()
    
    member_list = []
    for member in members:
        member_list.append(member.user.username)
    
    return member_list


def start_flask_server():
    socketio.run(app, debug=True, port=5001)

# bot_should_run = True

# def start_discord_bot():
#     global bot_should_run
#     while bot_should_run:
#         pyppo_bot.run(pyppo_token)
#         pass

# @app.route('/authorize')
# def authorize():
#     params = {
#         'client_id': discord_auth['client_id'],
#         'redirect_uri': 'http://127.0.0.1:5001/callback',
#         'response_type': 'code',
#         'scope': 'bot connections'
#     }

#     url = 'https://discord.com/api/oauth2/authorize?' + urlencode(params)

#     return redirect(url)


# @app.route('/callback')    
# def callback():
#     code = request.args.get('code')
    
#     # Check if the code is None
#     if code is None:
#         error = request.args.get('error')
#         return jsonify({'error': error}), 400
    
#     # Prepare data for the token request
#     data = {
#         'client_id': discord_auth['client_id'],
#         'client_secret': discord_auth['client_secret'],
#         'grant_type': 'authorization_code',
#         'code': code,
#         'redirect_uri': 'http://127.0.0.1:5001/callback',
#         'scope': 'bot connections'
#     }
    
#     # URL encode the data
#     data = urlencode(data)
    
#     # Send a POST request to the Discord token endpoint
#     response = requests.post('https://discord.com/api/oauth2/token', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    
#     # Get the access token from the response
#     access_token = response.json().get('access_token')
#     info = response.json()

#     return jsonify({"message" : "Callback received", "data" : data, 'info' : info})

# Start the pyppo_bot and Flask server concurrently
if __name__ == "__main__":
    # Start the Discord bot in a new thread
    # discord_thread = threading.Thread(target=start_discord_bot, daemon=True)
    # discord_thread.start()

    try:
        start_flask_server()
    except KeyboardInterrupt:
        bot_should_run = False

