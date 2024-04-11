from flask import Flask, jsonify, request, redirect
from flask_socketio import SocketIO, join_room, leave_room, send, emit
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity, unset_jwt_cookies, create_refresh_token, set_access_cookies, set_refresh_cookies, verify_jwt_in_request, get_jti, decode_token, get_jwt
from flask_cors import CORS

from discord.ext import commands
import discord  # Add this line
from werkzeug.security import generate_password_hash

from models.Room import Room
from models.User import User
from database import db

import spotipy
from spotipy.oauth2 import SpotifyOAuth

import asyncio
import requests
from urllib.parse import urlencode

import threading
from threading import Thread


app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*")
intents = discord.Intents.default()

pyppo_bot = commands.Bot(command_prefix='!', intents=intents)
pyppo_token = 'MTIyNjQ5Nzk1NzE3MjM0Njk0MQ.GApILx.O4hBAGwdEn_Q2i3-w09RQPgLYmTRzLLY0ACC8g'

discord_auth = {
    'client_id': '1226497957172346941',
    'client_secret': 'UA6DjTjHQdhllFYoiuVk7RsoE_C19cMR',
    'redirect_uri': 'http://127.0.0.1:5001/callback',
}


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
@pyppo_bot.command()
async def pinfo(ctx):
    await ctx.send("Hello, I am Pyppo! I am the manager of the playback that you will use later. If you want to play something, just type !pplay")
    
@pyppo_bot.command()
async def pchat(ctx):
    await ctx.send("I have no idea what you are talking about")
    
# --------------------- REAL-TIME EVENTS --------------------- #
@app.route('/rooms', methods=['GET'])
@jwt_required()
def get_my_rooms():
    host_id = get_jwt_identity()  # Get the host_id from the JWT identity
    my_rooms = Room.query.filter_by(host_id=host_id).all()  # Query for all rooms hosted by this user

    if not my_rooms:
        return jsonify({"error": "No rooms found"}), 404

    # Convert the rooms to a format that can be JSONified
    my_rooms = [{"id": room.id, "name": room.name, "room_type": room.room_type} for room in my_rooms]

    return jsonify({"my_rooms" : my_rooms}), 200

@app.route('/rooms/all', methods=['GET'])
def get_all_rooms():
    all_rooms = Room.query.all()  # Query for all rooms

    # Convert the rooms to a format that can be JSONified
    all_rooms = [{"id": room.id, "name": room.name, "room_type": room.room_type} for room in all_rooms]

    return jsonify({"all_rooms" : all_rooms}), 200

@app.route('/rooms', methods=['POST'])
@jwt_required()
def create_room():
    room_name = request.json['room_name']
    room_password = request.json.get('room_password')
    if room_password:
        room_type = 'private'
        hashed_password = generate_password_hash(room_password)  # Hash the password
    else:
        room_type = 'public'
        hashed_password = None

    host_id = get_jwt_identity()  # Get the host_id from the JWT identity

    new_room = Room(name=room_name, password=hashed_password, room_type=room_type, host_id=host_id)
    db.session.add(new_room)
    db.session.commit()
    return jsonify({"msg": f"Room {room_name} created successfully", "room_id": new_room.id})

@socketio.on('join')
def on_join(data):
    username = data['username']
    room = data['room']
    join_room(room)
    send({"msg": username + " has entered the room."}, room=room)
    
@socketio.on('leave')
def on_leave(data):
    username = data['username']
    room = data['room']
    leave_room(room)
    send({"msg": username + " has left the room."}, room=room)
    
@socketio.on('send_message')
def handle_send_message(data):
    msg = data['message']
    room = data['room']
    # Broadcast the message to all users in the room
    send({"msg": msg}, room=room)

@socketio.on('private_message')
def private_message(payload):
    recipient_session_id = users[payload['username']]
    message = payload['message']

    emit('new_private_message', message, room=recipient_session_id)
    
@socketio.on('typing')
def handle_typing(data):
    room = data['room']
    user = data['username']
    # Broadcast the typing event to all users in the room
    emit('user_typing', {'user': user}, room=room)

def start_flask_server():
    socketio.run(app, debug=True, port=5001)

bot_should_run = True

def start_discord_bot():
    global bot_should_run
    while bot_should_run:
        pyppo_bot.run(pyppo_token)
        pass

@app.route('/authorize')
def authorize():
    params = {
        'client_id': discord_auth['client_id'],
        'redirect_uri': 'http://127.0.0.1:5001/callback',
        'response_type': 'code',
        'scope': 'bot connections'
    }

    url = 'https://discord.com/api/oauth2/authorize?' + urlencode(params)

    return redirect(url)


@app.route('/callback')    
def callback():
    code = request.args.get('code')
    
    # Check if the code is None
    if code is None:
        error = request.args.get('error')
        return jsonify({'error': error}), 400
    
    # Prepare data for the token request
    data = {
        'client_id': discord_auth['client_id'],
        'client_secret': discord_auth['client_secret'],
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': 'http://127.0.0.1:5001/callback',
        'scope': 'bot connections'
    }
    
    # URL encode the data
    data = urlencode(data)
    
    # Send a POST request to the Discord token endpoint
    response = requests.post('https://discord.com/api/oauth2/token', data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    
    # Get the access token from the response
    access_token = response.json().get('access_token')
    info = response.json()

    return jsonify({"message" : "Callback received", "data" : data, 'info' : info})

# Start the pyppo_bot and Flask server concurrently
if __name__ == "__main__":
    # Start the Discord bot in a new thread
    discord_thread = threading.Thread(target=start_discord_bot, daemon=True)
    discord_thread.start()

    try:
        start_flask_server()
    except KeyboardInterrupt:
        bot_should_run = False

