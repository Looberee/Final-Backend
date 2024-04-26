from flask import Flask, request, jsonify, make_response, current_app, redirect, session, url_for, render_template
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity, unset_jwt_cookies, create_refresh_token, set_access_cookies, set_refresh_cookies, verify_jwt_in_request, get_jti, decode_token, get_jwt
from flask_session import Session
from flask_caching import Cache
from flask_socketio import SocketIO, emit
from flask_mail import Mail, Message
from flask_restx import Api, Resource, fields
from flask_redis import FlaskRedis


import concurrent.futures
from concurrent.futures import ThreadPoolExecutor


import random
from retrying import retry
import atexit

# End importing Flask Components

from sqlalchemy.exc import IntegrityError
from sqlalchemy import desc
from sqlalchemy import asc
#End import Flask Database

from models.User import User
from models.UserPlaylist import UserPlaylist
from models.UserPlaylistTrack import UserPlaylistTrack
from models.RecentTrack import RecentTrack
from models.Track import Track
from models.Artist import Artist
from models.UserPreference import UserPreference
from models.Recommendation import Recommendation
from models.RefreshToken import RefreshToken, insert_refresh_token
from models.Genre import Genre
from models.Room import Room
from models.Payment import Payment
from models.RoomMember import RoomMember
from models.Admin import Admin
from database import db

import asyncio
import aiohttp

import smtplib

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


import paypalrestsdk

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

import spotipy
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth
#End importing Spotify API


import cloudinary
from cloudinary import uploader
from cloudinary.uploader import upload
from cloudinary.utils import cloudinary_url
#End importing Cloudinary API

from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import cached_property
#End import werkzeug



import base64
import requests
from urllib.parse import urlencode
from base64 import b64encode
from datetime import datetime, timedelta
import time
import json
from threading import Thread

app = Flask(__name__, instance_relative_config=True)
# api.init_app(app)
# app.register_blueprint(api.blueprint)
# api = Api(app)
app.secret_key = 'Delta1006'


login_manager = LoginManager(app)
login_manager.init_app(app)

CORS(app, origins=["http://localhost:3000"], supports_credentials=True)  # Replace with your frontend URL
socketio = SocketIO(app, cors_allowed_origins="*")
redis = FlaskRedis(app)
cache = Cache(app, config={'CACHE_TYPE': 'simple'})

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


# End configuring

jwt = JWTManager(app)
jwt.init_app(app)

# End init JWTManager

db.init_app(app)
# End init DB

migrate = Migrate(app, db)
# End init Flask-Migrate

mail = Mail(app)
# End init Mail

@login_manager.user_loader
def load_user(user_id):
    # Load and return the user from the database based on user_id
    return User.query.get(user_id)

Session(app)

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

paypalrestsdk.configure({
    "mode": "sandbox",  # sandbox or live
    "client_id": "AfARXGhy5pQVvIf9tewEiRXNDZXQW8KhqC1BVL43euxM8XZkvY2fwP1JEu4Py1pJAOKdoKaDF38-JcRM",
    "client_secret": "EE1DL1xlFI32ZFXZBVnkDGVqXdYmyh43FuQHSZDkRGS_K8V6vvARRa3obHwnfsUgZdLitXXFJP1QBBHN" })

access_token = redis.get('spotify_access_token')

token_data = {
    'client_id': sp_oauth.client_id,
    'client_secret': sp_oauth.client_secret,
    'code': 'authorization_code',
    'grant_type': 'authorization_code',
    'redirect_uri': sp_oauth.redirect_uri,
}

cloudinary.config(
    cloud_name="dckgpl1ys",
    api_key="591486649953755",
    api_secret="t5VPVbTf9eUI3tzReLGPDNZyL8Q"
)
api = Api(app, doc='/api')

playlist_ns = api.namespace('personal', description='Personal playlists operations')

playlist_model = api.model('Playlist', {
    'id': fields.Integer,
    'name': fields.String,
    'tracks_count': fields.Integer,
    'encode_id': fields.String
})

track_model = api.model('Track', {
    'spotify_image_url': fields.String,
    'id': fields.Integer,
    'name': fields.String,
    'artists': fields.String,
    'genres': fields.String,
    'duration': fields.Integer,
    'release_date': fields.String,
    'spotify_id': fields.String,
    'is_favourite': fields.Boolean
})

artist_model = api.model('Artist', {
    'id': fields.Integer,
    'name': fields.String,
    'genres': fields.List(fields.String),
    'spotify_image_url': fields.String,
    'artist_id': fields.String,
    'followers': fields.Integer
})

playlist_create_model = api.model('PlaylistCreate', {
    'playlist_name': fields.String(required=True, description='Name of the playlist to be created')
})

@playlist_ns.route('/playlists')
class PersonalPlaylists(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @api.marshal_with(playlist_model, envelope='user_playlists')
    def get(self):
        """
        Retrieve all playlists for the current user.
        """
        current_user_id = get_jwt_identity()
        user_playlists = UserPlaylist.query.filter_by(user_id=current_user_id).all()
        playlists_info = []

        for playlist in user_playlists:
            tracks_count = UserPlaylistTrack.query.filter_by(user_playlist_id=playlist.id).count()
            playlist_info = {
                'id': playlist.id,
                'name': playlist.name,
                'tracks_count': tracks_count,
                'encode_id': playlist.encode_id
            }
            playlists_info.append(playlist_info)

        return playlists_info

    @api.doc(security='apikey')
    @jwt_required()
    @api.expect(playlist_create_model)
    @api.response(201, 'Playlist created successfully', playlist_model)
    def post(self):
        """
        Create a new playlist for the current user.
        """
        current_user_id = get_jwt_identity()
        playlist_name = api.payload.get('playlist_name')
        if not playlist_name:
            return {'message': 'Invalid request. Please provide a playlist name'}, 400
        user_playlists_count = UserPlaylist.query.filter_by(user_id=current_user_id).count()
        playlist_name = f'My playlist # {user_playlists_count + 1}'
        user_id = current_user_id
        new_playlist = UserPlaylist(name=playlist_name, user_id=user_id)
        db.session.add(new_playlist)
        db.session.commit()
        return {'message': 'Playlist created successfully', 'playlist_name': playlist_name}, 201

    @api.doc(security='apikey')
    @jwt_required()
    @api.response(204, 'Playlist updated successfully')
    def put(self):
        """
        Update a playlist for the current user.
        """
        # Your code to update a playlist goes here
        return {'message': 'Playlist updated successfully'}, 204

    @api.doc(security='apikey')
    @jwt_required()
    @api.response(204, 'Playlist deleted successfully')
    def delete(self):
        """
        Delete a playlist for the current user.
        """
        # Your code to delete a playlist goes here
        return {'message': 'Playlist deleted successfully'}, 204
    
@playlist_ns.route('/playlists/<string:encode_id>/tracks')
class PersonalPlaylistTracks(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @api.marshal_with(playlist_model, envelope='playlist')
    def get(self, encode_id):
        """
        Retrieve tracks for a specific playlist of the current user.
        """
        current_user_id = get_jwt_identity()
        playlist = UserPlaylist.query.filter_by(encode_id=encode_id, user_id=current_user_id).first()
        user_preference = UserPreference.query.filter_by(user_id=current_user_id).first()

        if playlist:
            tracks = UserPlaylistTrack.query.filter_by(user_playlist_id=playlist.id).all()
            tracks_info = []

            for user_playlist_track in tracks:
                track = Track.query.get(user_playlist_track.track_id)
                if track:
                    track_info = {
                        'spotify_image_url': track.cloudinary_img_url,
                        'id': track.id,
                        'name': track.name,
                        'artists': track.artists,
                        'genres': track.track_genres,
                        'duration': track.duration_ms,
                        'release_date': track.release_date,
                        'spotify_id': track.spotify_id,
                        'is_favourite': track.id in [t.id for t in user_preference.favorite_tracks],
                    }
                    tracks_info.append(track_info)

            # Include playlist name in the response
            playlist_info = {
                'id': playlist.id,
                'name': playlist.name,
                'tracks': tracks_info
            }

            return {'playlist': playlist_info}
        else:
            return {'error': 'Playlist not found'}, 404

@playlist_ns.route('/playlists/<string:playlist_id>/track/<string:track_id>')
class PersonalPlaylistTrack(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    def post(self, playlist_id, track_id):
        """
        Add a track to a specific playlist of the current user.
        """
        current_user_id = get_jwt_identity()
        playlist = UserPlaylist.query.filter_by(encode_id=playlist_id, user_id=current_user_id).first()

        if playlist:
            # Your code to add a track to the playlist goes here
            return {'message': 'Track added to the playlist successfully'}, 201
        else:
            return {'error': 'Playlist not found'}, 404

    @api.doc(security='apikey')
    @jwt_required()
    def delete(self, playlist_id, track_id):
        """
        Remove a track from a specific playlist of the current user.
        """
        current_user_id = get_jwt_identity()
        playlist = UserPlaylist.query.filter_by(encode_id=playlist_id, user_id=current_user_id).first()

        if playlist:
            # Your code to remove a track from the playlist goes here
            return {'message': 'Track removed from the playlist successfully'}, 204
        else:
            return {'error': 'Playlist not found'}, 404
        

    
artist_model = api.model('Artist', {
    'id': fields.Integer,
    'name': fields.String,
    'genres': fields.List(fields.String),
    'spotify_image_url': fields.String,
    'artist_id': fields.String,
    'followers': fields.Integer
})
    
favourites_ns = api.namespace('personal/favourites', description='Personal favorites tracks operations')

@favourites_ns.route('/artists')
class PersonalFavoriteArtists(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @api.marshal_with(artist_model, envelope='favorite_artists')
    def get(self):
        """
        Retrieve personal favorite artists for the current user.
        """
        current_user_id = get_jwt_identity()
        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
        if user_pref:
            return user_pref.favorite_artists, 200
        else:
            return {'message': 'No favorite artists found'}, 404

    @api.doc(security='apikey')
    @jwt_required()
    def post(self):
        """
        Add a personal favorite artist for the current user.
        """
        current_user_id = get_jwt_identity()
        artist_id = request.json.get('artist_id')

        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
        if user_pref:
            artist = Artist.query.filter_by(spotify_id=artist_id).first()
            if artist:
                if artist not in user_pref.favorite_artists:
                    user_pref.favorite_artists.append(artist)
                    db.session.commit()
                    return {'message': 'Artist added to favorites successfully'}, 200
                else:
                    return {'message': 'Artist already exists in favorites'}, 400
            else:
                return {'message': 'Artist not found'}, 404
        else:
            return {'message': 'User preference not found'}, 404

    @api.doc(security='apikey')
    @jwt_required()
    def delete(self):
        """
        Delete a personal favorite artist for the current user.
        """
        current_user_id = get_jwt_identity()
        artist_id = request.json.get('artist_id')

        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
        if user_pref:
            artist = Artist.query.filter_by(spotify_id=artist_id).first()
            if artist:
                if artist in user_pref.favorite_artists:
                    user_pref.favorite_artists.remove(artist)
                    db.session.commit()
                    return {'message': 'Artist removed from favorites successfully'}, 200
                else:
                    return {'message': 'Artist not found in favorites'}, 404
            else:
                return {'message': 'Artist not found'}, 404
        else:
            return {'message': 'User preference not found'}, 404

@favourites_ns.route('/artist/check')
class CheckFavoriteArtist(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    def post(self):
        """
        Check if an artist is a personal favorite for the current user.
        """
        current_user_id = get_jwt_identity()
        artist_id = request.json.get('artist_id')

        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
        if user_pref:
            artist = Artist.query.filter_by(spotify_id=artist_id).first()
            if artist:
                if artist in user_pref.favorite_artists:
                    return {'favourite': True}, 200
                else:
                    return {'favourite': False}, 200
            else:
                return {'message': 'Artist not found'}, 404
        else:
            return {'message': 'User preference not found'}, 404
        
personal_ns = api.namespace('personal', description='Personal operations')

@personal_ns.route('/recent/tracks')
class PersonalRecentTracks(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @api.marshal_with(track_model, envelope='recent_tracks')
    def get(self):
        """
        Retrieve recent tracks for the current user.
        """
        current_user_id = get_jwt_identity()
        recent_tracks_data = RecentTrack.query.filter_by(user_id=current_user_id).order_by(desc(RecentTrack.played_at)).limit(5)
        recent_tracks = []
        for recent_track_data in recent_tracks_data:
            track = Track.query.filter_by(id=recent_track_data.track_id).first()
            if track:
                recent_tracks.append({
                    'id': track.id,
                    'name': track.name,
                    'artists': track.artists.split(','),
                    'duration': track.duration,
                    'genres': track.genres,
                    'release_date': track.release_date,
                    'spotify_image_url': track.spotify_image_url,
                    'spotify_id': track.spotify_id
                })
        return recent_tracks, 200

    @api.doc(security='apikey')
    @jwt_required()
    def post(self):
        """
        Add a recent track for the current user.
        """
        current_user_id = get_jwt_identity()
        data = request.json
        spotify_id = data.get('spotify_id')
        played_at_timestamp = data.get('played_at')  # Assuming played_at is a timestamp
        played_at = datetime.fromtimestamp(played_at_timestamp / 1000)
        
        # Your logic to add a recent track goes here
        
        return {'message': 'Recent track added successfully'}, 200

@personal_ns.route('/favourites/tracks')
class PersonalFavoriteTracks(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @api.marshal_with(track_model, envelope='favourite_tracks')
    def get(self):
        """
        Retrieve favorite tracks for the current user.
        """
        current_user_id = get_jwt_identity()
        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
        if user_pref:
            favorite_tracks = user_pref.favorite_tracks
            serialized_tracks = []
            for track in favorite_tracks:
                serialized_tracks.append({
                    'id': track.id,
                    'name': track.name,
                    'artists': track.artists.split(','),
                    'duration': track.duration,
                    'genres': track.genres,
                    'release_date': track.release_date,
                    'spotify_image_url': track.spotify_image_url,
                    'spotify_id': track.spotify_id
                })
            return serialized_tracks, 200
        else:
            return {'message': 'No favorite tracks found'}, 404

    @api.doc(security='apikey')
    @jwt_required()
    def post(self):
        """
        Add a favorite track for the current user.
        """
        current_user_id = get_jwt_identity()
        data = request.json
        spotify_id = data.get('spotify_id')

        # Your logic to add a favorite track goes here

        return {'message': 'Track added to favorites successfully'}, 200

    @api.doc(security='apikey')
    @jwt_required()
    def delete(self):
        """
        Delete a favorite track for the current user.
        """
        current_user_id = get_jwt_identity()
        spotify_id = request.json.get('spotify_id')
        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
        if user_pref:
            track = Track.query.filter_by(spotify_id=spotify_id).first()
            if track:
                user_pref.favorite_tracks.remove(track)
                db.session.commit()
                return {'message': 'Track removed from favorites successfully'}, 200
            else:
                return {'error': 'Track not found'}, 404
        else:
            return {'message': 'No favorite tracks found'}, 404

@personal_ns.route('/favourites/track/check')
class CheckFavoriteTrack(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    def post(self):
        """
        Check if a track is a favorite for the current user.
        """
        current_user_id = get_jwt_identity()
        spotify_id = request.json.get('spotify_id')
        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
        if user_pref:
            is_favorite = any(track.spotify_id == spotify_id for track in user_pref.favorite_tracks)
            return {'favourite': is_favorite}, 200
        else:
            return {'message': 'User preference not found'}, 404

retry.stop_max_attempt_number = 3
retry.wait_fixed = 1000

def refresh_spotify_token():
    # Refresh Spotify access token
    token_info = sp_oauth.refresh_access_token(redis.get('spotify_refresh_token').decode('utf-8'))
    redis.set('spotify_access_token', token_info['access_token'])
    return token_info['access_token']

# @app.route('/transfer-playback', methods=['POST'])
# def transfer_playback():
#     access_token = redis.get('spotify_access_token').decode('utf-8')  # Decode the token
#     target_device_id = request.json.get('target_device_id')  # Get the target device ID from the request

#     # Initialize Spotify client
#     sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

#     try:
#         # Transfer playback to the specified device
#         sp.transfer_playback(device_id=target_device_id, force_play=True)
#         return jsonify({'success': True, 'message': 'Playback transferred successfully.'}), 200
#     except spotipy.SpotifyException as e:
#         return jsonify({'success': False, 'message': str(e)}), 400
    
# @app.route('/active-devices')
# def get_active_devices():
#     access_token = redis.get('spotify_access_token')
    
#     if access_token is None:
#         return jsonify({'message': 'Access token not found in Redis.'}), 404
    
#     access_token = access_token.decode('utf-8')  # Decode the token
    
#     # Initialize Spotify client
#     sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
#     # Retrieve user's active devices
#     devices = sp.devices()
#     active_devices = []
#     for device in devices['devices']:
#         if device['is_active']:
#             active_devices.append({
#                 'id': device['id'],
#                 'name': device['name']
#             })

#     if not active_devices:
#         return jsonify({'message': 'No active devices found.'}), 404
    
#     return jsonify({'devices': active_devices})

# @app.route('/playback/play', methods=['POST'])
# @jwt_required()
# def pyppo_play_track():
#     access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
#     sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

#     track_uri = request.json.get('trackUri')
#     device_id = request.json.get('myDeviceId')
    
#     @retry(stop_max_attempt_number=3, wait_fixed=1000, retry_on_result=lambda result: result is False)
#     def start_playback():
#         try:
#             sp.start_playback(device_id=device_id, uris=[track_uri])
#             time.sleep(1)
#             return True  # Success
#         except spotipy.SpotifyException as e:
#             if e.http_status == 404:  # No active device found
#                 print("No active device found. Retrying...")
#                 refresh_spotify_token()
#                 return False  # Retry
#             elif e.http_status == 500:
#                 refresh_spotify_token()
#             else:
#                 raise  # Raise exception for other errors

#     try:
#         start_playback()
#         return jsonify({'success': True, 'message': 'Playback started successfully.'}), 200
#     except Exception as e:
#         return jsonify({'success': False, 'message': 'Failed to start playback: ' + str(e)}), 500
    
success_model = api.model('Success', {
    'success': fields.Boolean(description='Indicates whether the operation was successful'),
    'message': fields.String(description='Additional message related to the operation')
})

@api.route('/playback/play')
class PlaybackPlay(Resource):
    @api.doc(description='Start playback of a track on a specified device')
    @api.response(200, 'Success', success_model)
    @api.response(400, 'Bad Request', success_model)
    def post(self):
        access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        track_uri = api.payload.get('trackUri')
        device_id = api.payload.get('myDeviceId')

        @retry(stop_max_attempt_number=3, wait_fixed=1000, retry_on_result=lambda result: result is False)
        def start_playback():
            try:
                sp.start_playback(device_id=device_id, uris=[track_uri])
                time.sleep(1)
                return True  # Success
            except spotipy.SpotifyException as e:
                if e.http_status == 404:  # No active device found
                    print("No active device found. Retrying...")
                    refresh_spotify_token()
                    return False  # Retry
                elif e.http_status == 500:
                    refresh_spotify_token()
                else:
                    raise  # Raise exception for other errors

        try:
            start_playback()
            return {'success': True, 'message': 'Playback started successfully'}, 200
        except Exception as e:
            return {'success': False, 'message': 'Failed to start playback: ' + str(e)}, 500

@api.route('/playback/pause')
class PlaybackPause(Resource):
    @api.doc(description='Pause playback on a specified device')
    @api.response(200, 'Success', success_model)
    @api.response(400, 'Bad Request', success_model)
    def post(self):
        access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        device_id = api.payload.get('myDeviceId')

        sp.pause_playback(device_id=device_id)

        return {'success': True, 'message': 'Playback paused successfully'}, 200

@api.route('/playback/resume')
class PlaybackResume(Resource):
    @api.doc(description='Resume playback on a specified device')
    @api.response(200, 'Success', success_model)
    @api.response(400, 'Bad Request', success_model)
    def post(self):
        access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        device_id = api.payload.get('myDeviceId')

        sp.start_playback(device_id=device_id)

        return {'success': True, 'message': 'Playback resumed successfully'}, 200

response_model = api.model('Response', {
    'success': fields.Boolean(description='Indicates whether the operation was successful'),
    'message': fields.String(description='Additional message related to the operation'),
    'nextTrack': fields.Nested(api.model('NextTrack', {
        'name': fields.String(description='Name of the next track'),
        'spotify_id': fields.String(description='Spotify ID of the next track'),
        'artists': fields.List(fields.String(description='List of artists of the next track')),
        'spotify_image_url': fields.String(description='URL of the image associated with the next track'),
        'duration': fields.Integer(description='Duration of the next track in milliseconds')
    })),
    'previousTrack': fields.Nested(api.model('PreviousTrack', {
        'name': fields.String(description='Name of the previous track'),
        'spotify_id': fields.String(description='Spotify ID of the previous track'),
        'artists': fields.List(fields.String(description='List of artists of the previous track')),
        'spotify_image_url': fields.String(description='URL of the image associated with the previous track'),
        'duration': fields.Integer(description='Duration of the previous track in milliseconds')
    }))
})

# Define routes
@api.route('/playback/next')
class NextTrack(Resource):
    @api.doc(description='Play the next track on the specified device')
    @api.expect(api.model('NextTrackRequest', {
        'myDeviceId': fields.String(description='ID of the target device')
    }))
    @api.marshal_with(response_model)
    def post(self):
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = request.json.get('myDeviceId')

        playlists = sp.featured_playlists(limit=7)['playlists']['items']
        random_playlist = random.choice(playlists)
        playlist_id = random_playlist['id']
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']

        # Select one track randomly
        current_track_info = random.choice(tracks)
        print("Current track info: ", current_track_info['track'].get('name'))  # Print the information of the current track
        
        response_data = {
            'success': True,
            'message': 'Next track command sent successfully.',
            'nextTrack': {
                'name' : current_track_info['track'].get('name'),
                'spotify_id' : current_track_info['track'].get('id'),
                'artists' : [artist['name'] for artist in current_track_info['track'].get('artists')],
                'spotify_image_url' : current_track_info['track'].get('album').get('images')[0].get('url'),
                'duration' : current_track_info['track'].get('duration_ms')
            }
        }
        
        sp.start_playback(device_id=device_id, uris=[current_track_info['track'].get('uri')])
        
        return response_data, 200

@api.route('/playback/previous')
class PreviousTrack(Resource):
    @api.doc(description='Play the previous track on the specified device')
    @api.expect(api.model('PreviousTrackRequest', {
        'myDeviceId': fields.String(description='ID of the target device')
    }))
    @api.marshal_with(response_model)
    def post(self):
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = request.json.get('myDeviceId')

        playlists = sp.featured_playlists(limit=7)['playlists']['items']
        random_playlist = random.choice(playlists)
        playlist_id = random_playlist['id']
        results = sp.playlist_tracks(playlist_id)
        tracks = results['items']

        # Select one track randomly
        current_track_info = random.choice(tracks)
        print("Current track info: ", current_track_info['track'].get('name'))  # Print the information of the current track
        
        response_data = {
            'success': True,
            'message': 'Previous track command sent successfully.',
            'previousTrack': {
                'name' : current_track_info['track'].get('name'),
                'spotify_id' : current_track_info['track'].get('id'),
                'artists' : [artist['name'] for artist in current_track_info['track'].get('artists')],
                'spotify_image_url' : current_track_info['track'].get('album').get('images')[0].get('url'),
                'duration' : current_track_info['track'].get('duration_ms')
            }
        }
        
        sp.start_playback(device_id=device_id, uris=[current_track_info['track'].get('uri')])
        
        return response_data, 200

@api.route('/playback/shuffle')
class Shuffle(Resource):
    @api.doc(description='Toggle shuffle mode on the specified device')
    @api.expect(api.model('ShuffleRequest', {
        'myDeviceId': fields.String(description='ID of the target device'),
        'shuffleState': fields.Boolean(description='True to enable shuffle, False to disable')
    }))
    @api.marshal_with(response_model)
    def post(self):
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = request.json.get('myDeviceId')
        shuffle_state = request.json.get('shuffleState')

        sp.shuffle(shuffle_state, device_id=device_id)
        return {'success': True, 'message': f'Shuffle {"enabled" if shuffle_state else "disabled"} successfully.'}, 200

@api.route('/playback/repeat')
class Repeat(Resource):
    @api.doc(description='Set repeat mode on the specified device')
    @api.expect(api.model('RepeatRequest', {
        'myDeviceId': fields.String(description='ID of the target device'),
        'repeatState': fields.String(description='Repeat mode: "track", "context", or "off"')
    }))
    @api.marshal_with(response_model)
    def post(self):
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = request.json.get('myDeviceId')
        repeat_state = request.json.get('repeatState')

        sp.repeat(repeat_state, device_id=device_id)
        return {'success': True, 'message': f'Repeat mode set to {repeat_state} successfully.'}, 200

@api.route('/playback/seek')
class Seek(Resource):
    @api.doc(description='Seek playback to a specified position on the currently playing track')
    @api.expect(api.model('SeekRequest', {
        'myDeviceId': fields.String(description='ID of the target device'),
        'newPositionMs': fields.Integer(description='New position in milliseconds')
    }))
    @api.marshal_with(response_model)
    def post(self):
        data = request.json
        new_position_ms_str = data.get('newPositionMs')
        
        if new_position_ms_str is not None:
            new_position_ms = int(new_position_ms_str)
            access_token = redis.get('spotify_access_token').decode('utf-8')
            sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
            playback_info = sp.current_playback()

            # Check if a track is currently playing
            if playback_info and playback_info['is_playing']:
                # Check if repeat mode is active
                if playback_info['repeat_state'] != 'off':
                    # Temporarily disable repeat mode
                    sp.repeat('off')

                # Seek to the new position
                sp.seek_track(new_position_ms)

                # Re-enable repeat mode if it was active
                if playback_info['repeat_state'] != 'off':
                    sp.repeat(playback_info['repeat_state'])

                return {'success': True, 'message': f'Seeked to {new_position_ms} milliseconds'}, 200
            else:
                return {'success': False, 'message': 'No track is currently playing'}, 400
        else:
            return {'success': False, 'message': 'Invalid new position'}, 400

@api.route('/playback/current_track_position')
class CurrentTrackPosition(Resource):
    @api.doc(description='Get the current position of the playback in milliseconds')
    @api.marshal_with(response_model)
    def get(self):
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        # Get the current playback information
        playback_info = sp.current_playback()

        # Check if a track is currently playing
        if playback_info and playback_info['is_playing']:
            # Get the current track position
            current_track_position = playback_info['progress_ms']
            return {'success': True, 'message': 'Current track position retrieved successfully.', 'current_track_position': current_track_position}, 200
        else:
            return {'success': False, 'message': 'No track is currently playing', 'current_track_position': 0}, 404
        
genre_model = api.model('Genre', {
    'id': fields.Integer(description='The unique identifier for the genre'),
    'genre_name': fields.String(description='The name of the genre'),
    'genre_image': fields.String(description='The URL of the image representing the genre')
})

tracks_model = api.model('Tracks', {
    'name': fields.String(description='The name of the track'),
    'spotify_id': fields.String(description='The Spotify ID of the track'),
    'album_id': fields.String(description='The Spotify ID of the album'),
    'artists': fields.String(description='The name of the artist(s)'),
    'duration': fields.Integer(description='The duration of the track in milliseconds'),
    'popularity': fields.Integer(description='The popularity score of the track'),
    'preview_url': fields.String(description='The URL of the track preview'),
    'release_date': fields.String(description='The release date of the track'),
    'album_name': fields.String(description='The name of the album'),
    'spotify_image_url': fields.String(description='The URL of the album image')
})

@api.route('/recommendation/genres')
class RecommendGenres(Resource):
    @api.doc(description='Get recommended genres')
    @api.marshal_with(genre_model)
    def get(self):
        # Fetch genres from database and format the response
        genres = Genre.query.all()
        genres_list = [{'id': genre.id, 'genre_name': genre.genre_name, 'genre_image': genre.cloudinary_image_url} for genre in genres]
        return {'genres': genres_list}

@api.route('/recommendation/genres/<string:genre_name>')
class RecommendTracksByGenre(Resource):
    @api.doc(params={'genre_name': 'The name of the genre'})
    @api.marshal_with(tracks_model)
    def get(self, genre_name):
        access_token = redis.get('spotify_access_token').decode('utf-8') 
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        try:
            # Fetch tracks by genre using Spotify API
            formatted_tracks = fetch_tracks_by_genre(sp, genre_name)
            return {'formatted_tracks': formatted_tracks}
        except spotipy.SpotifyException as e:
            return {'error': str(e)}

# Helper function to fetch tracks by genre from Spotify API
def fetch_tracks_by_genre(sp, genre_name):
    tracks_info = sp.recommendations(seed_genres=[genre_name], limit=30)['tracks']
    formatted_tracks = []
    for track_info in tracks_info:
        formatted_track = {
            "name": track_info["name"],
            "spotify_id": track_info["id"],
            "album_id": track_info["album"]["id"],
            "artists": ', '.join([artist["name"] for artist in track_info["artists"]]),
            "duration": track_info["duration_ms"],
            "popularity": track_info["popularity"],
            "preview_url": track_info["preview_url"],
            "release_date": track_info["album"]["release_date"],
            "album_name": track_info["album"]["name"],
            "spotify_image_url": track_info["album"]["images"][0]["url"]  # Assuming the first image is the main one
        }
        formatted_tracks.append(formatted_track)
    return formatted_tracks

if __name__ == "__main__":
    app.run(debug=True, port=5003)
