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
from models.RoomTrack import RoomTrack
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


with app.app_context():
    db.create_all()
    db.session.commit()
    print("TABLES CREATED")
    
def pyppo_encode_id(id):
    return base64.b64encode(str(id).encode()).decode()

def pyppo_decode_id(id):
    return int(base64.b64decode(id).decode())

#All endpoints must return a jsonify data

@app.route('/')
def index():
    return jsonify({"Status" : "OK"}, 200)

def fetch_playlist_tracks(sp, playlist_id):
    playlist = sp.playlist(playlist_id)
    tracks = playlist["tracks"]["items"]
    return random.sample(tracks, 6)

def format_tracks(tracks):
    return [{
        'id': i + 1,
        'spotify_id': track['track']['id'],
        'name': track['track']['name'],
        'artists': [artist['name'] for artist in track['track']['artists']],
        'duration': track['track']['duration_ms'],
        'spotify_image_url': track['track']['album']['images'][0]['url']
    } for i, track in enumerate(tracks)]

@app.route('/home')
def get_pyppo_dashboard():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
    tracks = Track.query.with_entities(Track.id, Track.spotify_id, Track.name, Track.artists, Track.cloudinary_img_url).order_by(Track.popularity.desc()).limit(6).all()
    tracks = [track._asdict() for track in tracks] 

    # Define playlist IDs
    playlist_ids = ['6DZ46o6pDDIbqXzK5PN3qJ', '37i9dQZF1EVHGWrwldPRtj', '37i9dQZF1EQp9BVPsNVof1']

    # Fetch playlist tracks concurrently
    with concurrent.futures.ThreadPoolExecutor() as executor:
        playlists = executor.map(lambda playlist_id: fetch_playlist_tracks(sp, playlist_id), playlist_ids)

    # Format tracks
    formatted_tracks = [format_tracks(tracks) for tracks in playlists]

    # Fetch EDM artists
    edm_artists = sp.search(q='genre:edm', type='artist', limit=6)['artists']['items']

    # Format EDM artists
    formatted_edm_artists = [{
        "id": i + 1,
        "name": edm_artist["name"],
        "artist_id": edm_artist["id"],
        "popularity": edm_artist["popularity"],
        "spotify_image_url": edm_artist["images"][0]["url"] if edm_artist["images"] else None
    } for i, edm_artist in enumerate(edm_artists)]
    

    return jsonify({
        'tracks' : tracks,
        'ncs_tracks': formatted_tracks[0],
        'relax_tracks': formatted_tracks[1],
        'electronic_tracks': formatted_tracks[2],
        'edm_artists': formatted_edm_artists
    })


@app.route('/cookies')
def get_cookies():
    cookies = request.cookies

    # Print the contents of each cookie
    for cookie_name, cookie_value in cookies.items():
        print("--------------------")
        print(f"Cookie '{cookie_name}': {cookie_value}")
        print("--------------------")

    return "Check your console for cookie information!"

# ----------- TRACKS --------------- #
@app.route('/tracks/<path:track_id>')
def get_pyppo_tracks_by_id(track_id):
    sp = spotipy.Spotify(auth_manager=sp_oauth)

    try:
        # Get track information using the Spotify API
        track_info = sp.track(track_id)

        # Extract relevant information from the track_info dictionary
        response = {
            'name': track_info['name'],
            'artist': track_info['artists'][0]['name'],
            'album': track_info['album']['name'],
            'release_date': track_info['album']['release_date'],
            'uri': track_info['uri'],
            'image_url': track_info['album']['images'][0]['url'] if 'images' in track_info['album'] else None
        }

        return jsonify(response)

    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})
    
    
    
# -------------- SEARCH -------------------- #    
@app.route('/search')
def get_pyppo_search_by_query():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)  
    search_query = request.args.get('query')

    try:
        # Search for tracks in the database
        database_tracks = Track.query.filter(Track.name.ilike(f'%{search_query}%')).limit(6).all()
        track_info = []

        # Process tracks from the database
        for track in database_tracks:
            track_info.append({
                'type': 'track',
                'id': track.id,
                'spotify_id': track.spotify_id,
                'name': track.name,
                'artists': track.artists,
                'duration' : track.duration_ms,
                'spotify_image_url': track.cloudinary_img_url
            })
            
        # Check if there are enough tracks in the database
        if len(track_info) < 6:
            # Determine how many additional tracks are needed
            remaining_tracks_count = 6 - len(track_info)

            # Search for additional tracks using the Spotify API
            spotify_results = sp.search(q=search_query, type='track', limit=remaining_tracks_count)
            tracks_from_spotify = spotify_results.get('tracks', {}).get('items', [])

            # Extract relevant information from each track and add it to the response
            for track in tracks_from_spotify:
                # Add track information to the response
                track_info.append({
                    'type': 'track',
                    'id' : tracks_from_spotify.index(track) + 1,
                    'spotify_id': track['id'],
                    'name': track['name'],
                    'artists': track['artists'][0]['name'],
                    'duration': track['duration_ms'],
                    'spotify_image_url': track['album']['images'][0]['url']
                })

        # Search for artists in the database
        database_artists = Artist.query.filter(Artist.name.ilike(f'%{search_query}%')).limit(6).all()
        artist_info = []

        # Process artists from the database
        for artist in database_artists:
            artist_info.append({
                'type': 'artist',
                'id': artist.id,
                'name': artist.name,
                'artist_id': artist.spotify_id,
                'spotify_image_url': artist.cloudinary_artist_image_url
            })
            
        # Check if there are enough artists in the database
        if len(artist_info) < 6:
            # Determine how many additional artists are needed
            remaining_artists_count = 6 - len(artist_info)

            # Search for additional artists using the Spotify API
            spotify_artist_results = sp.search(q=search_query, type='artist', limit=remaining_artists_count)
            artists_from_spotify = spotify_artist_results.get('artists', {}).get('items', [])

            # Extract relevant information from each artist and add it to the response
            for artist in artists_from_spotify:
                # Add artist information to the response
                artist_info.append({
                    'type': 'artist',
                    'id' : artists_from_spotify.index(artist) + 1,
                    'name': artist['name'],
                    'artist_id': artist['id'],
                    'spotify_image_url': artist['images'][0]['url'] if artist['images'] else None
                })

        return jsonify({'search_results': track_info, 'artists_results' :artist_info})

    except spotipy.SpotifyException as e:
        # Handle Spotify API errors
        return jsonify({'error': str(e)}), 500

# ------------------------ PERSONAL -------------------------- #
@app.route('/personal/playlists', methods=['GET'])
@jwt_required()
def get_all_pyppo_user_playlists():
    current_user_id = get_jwt_identity()
    user_playlists = UserPlaylist.query.filter_by(user_id=current_user_id).all()
    playlists_info = []

    for playlist in user_playlists:
        tracks_count = UserPlaylistTrack.query.filter_by(user_playlist_id=playlist.id).count()
        playlist_info = {
            'id': playlist.id,
            'name': playlist.name,
            'tracks_count': tracks_count,
            'encode_id' : playlist.encode_id
        }
        playlists_info.append(playlist_info)

    return jsonify({'user_playlists': playlists_info})
    
@app.route('/personal/playlists', methods=['POST'])
@jwt_required()
def create_pyppo_user_playlists_by_id():
    current_user_id = get_jwt_identity()
    user_playlists_count = UserPlaylist.query.filter_by(user_id=current_user_id).count()
    playlist_name = f'My playlist # {user_playlists_count + 1}'
    user_id = current_user_id
    new_playlist = UserPlaylist(name=playlist_name, user_id=user_id)
    db.session.add(new_playlist)
    db.session.commit()
    return jsonify({'message': 'Playlist created successfully', 'playlist_name': playlist_name})


@app.route('/personal/playlists', methods=['PUT'])
@jwt_required()
def edit_pyppo_user_playlist_by_id():
    data = request.json
    encode_id = data.get('encode_id')
    new_name = data.get('new_name')  # Use 'name' to retrieve the new name
    # Find the playlist by ID
    playlist = UserPlaylist.query.filter_by(encode_id=encode_id).first()  # Use .first() instead of .all()
    if playlist:
        current_user_id = get_jwt_identity()
        if playlist.user_id == current_user_id:  # Check if the playlist belongs to the current user

            playlist.name = new_name
            # Commit the changes to the database
            db.session.commit()
            return jsonify({'message': 'Playlist name updated successfully'})
        else:
            return jsonify({'error': 'Unauthorized'}), 401
    else:
        return jsonify({'error': 'Playlist not found'}), 404

@app.route('/personal/playlists', methods=['DELETE'])
@jwt_required()
def delete_pyppo_user_playlists_by_id():
    current_user_id = get_jwt_identity()
    data = request.json
    encode_id = data.get('encode_id')
    playlist = UserPlaylist.query.filter_by(encode_id=encode_id, user_id=current_user_id).first()
    if playlist:
        current_user_id = get_jwt_identity()
        if playlist.user_id == current_user_id:  # Check if the playlist belongs to the current user
            db.session.delete(playlist)
            db.session.commit()
            return jsonify({'message': 'Playlist deleted successfully'})
        else:
            return jsonify({'error': 'Unauthorized'}), 401
    else:
        return jsonify({'error': 'Playlist not found'}), 404

    
@app.route('/personal/playlists/<path:encode_id>/tracks', methods=['GET'])
@jwt_required()
def get_pyppo_user_playlists_by_id(encode_id):
    current_user_id = get_jwt_identity()
    playlist = UserPlaylist.query.filter_by(encode_id=encode_id, user_id = current_user_id).first()
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
                    'genres' : track.track_genres,
                    'duration': track.duration_ms,
                    'release_date': track.release_date,
                    'spotify_id' : track.spotify_id,
                    'is_favourite': track.id in [t.id for t in user_preference.favorite_tracks],  # Add this line
                }
                tracks_info.append(track_info)
        
        # Include playlist name in the response
        playlist_info = {
            'id': playlist.id,
            'name': playlist.name,
            'tracks': tracks_info
        }

        return jsonify({'playlist': playlist_info})
    else:
        return jsonify({'error': 'Playlist not found'}), 404

    
@app.route('/personal/playlists/<path:playlist_id>/track/<path:track_id>', methods=['POST'])
@jwt_required()
def add_track_to_pyppo_user_playlist(playlist_id, track_id):
    current_user_id = get_jwt_identity()
    playlist = UserPlaylist.query.filter_by(encode_id=playlist_id, user_id=current_user_id).first()
    if playlist:
        # Check if the track exists in the Track model
        track = Track.query.filter_by(spotify_id=track_id).first()
        if track:
            existing_track = UserPlaylistTrack.query.filter_by(user_playlist_id=playlist.id, track_id=track.id).first()
            if existing_track:
                return jsonify({'error': 'Track already exists in the playlist'}), 400

            # Track exists, add it to the user's playlist
            new_playlist_track = UserPlaylistTrack(user_playlist_id=playlist.id, track_id=track.id)
            db.session.add(new_playlist_track)
            db.session.commit()
            return jsonify({'message': 'Track added to the playlist successfully'})
        else:
            # Track does not exist, fetch it from Spotify API
            access_token = redis.get('spotify_access_token').decode('utf-8')
            sp = Spotify(auth_manager=sp_oauth, auth = access_token)
            
            track_data = sp.track(track_id)
            artist_detail = sp.artist(track_data['artists'][0]['id'])
            genres = ', '.join(artist_detail['genres'])
            
            if track_data:
                # Upload the track image to Cloudinary
                cloudinary_img_url = upload_image_to_cloudinary(track_data['album']['images'][0]['url'])

                # Create a new track instance with Cloudinary image URL
                new_track = Track(
                    spotify_id=track_id,
                    name=track_data['name'],
                    album_id=track_data['album']['id'],
                    artists=','.join([artist['name'] for artist in track_data['artists']]),
                    duration_ms=track_data['duration_ms'],
                    popularity=track_data['popularity'],
                    preview_url=track_data['preview_url'],
                    release_date=track_data['album']['release_date'],
                    album_name=track_data['album']['name'],
                    album_release_date=track_data['album']['release_date'],
                    cloudinary_img_url=cloudinary_img_url, # Cloudinary image URL
                    track_genres = genres,
                )
                
                db.session.add(new_track)
                db.session.commit()

                # Add the new track to the user's playlist
                new_playlist_track = UserPlaylistTrack(user_playlist_id=playlist.id, track_id=new_track.id)
                db.session.add(new_playlist_track)
                db.session.commit()
                
                return jsonify({'message': 'Track added to the playlist successfully'})
            else:
                return jsonify({'error': 'Failed to fetch track data from Spotify API'}), 500
    else:
        return jsonify({'error': 'Playlist not found'}), 404
    
@app.route('/personal/playlists/<path:playlist_id>/track/<path:track_id>', methods=['DELETE'])
@jwt_required()
def remove_track_from_pyppo_user_playlist(playlist_id, track_id):
    current_user_id = get_jwt_identity()
    playlist = UserPlaylist.query.filter_by(encode_id=playlist_id, user_id = current_user_id).first()
    if playlist:
        track = Track.query.filter_by(id=track_id).first()
        if track:
            playlist_track = UserPlaylistTrack.query.filter_by(user_playlist_id=playlist.id, track_id=track.id).first()
            if playlist_track:
                db.session.delete(playlist_track)
                db.session.commit()
                return jsonify({'message': 'Track removed from the playlist successfully'})
            else:
                return jsonify({'error': 'Track not found in the playlist'}), 404
        else:
            return jsonify({'error': 'Track not found'}), 404
    else:
        return jsonify({'error': 'Playlist not found'}), 404

    
@app.route('/personal/recent/tracks', methods=['POST'])
@jwt_required()
def add_pyppo_recent_track():
    data = request.json
    spotify_id = data.get('spotify_id')
    played_at_timestamp = data.get('played_at')  # Assuming played_at is a timestamp
    user_id = get_jwt_identity()
    
    # Convert timestamp to datetime object
    played_at = datetime.fromtimestamp(played_at_timestamp / 1000)  # Divide by 1000 to convert milliseconds to seconds
    
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Decode the token
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    track_details = sp.track(spotify_id)

    if track_details:
        # Check if the track exists in the Track model
        track = Track.query.filter_by(spotify_id=spotify_id).first()
        
        artist_detail = sp.artist(track_details['artists'][0]['id'])
        genres = ', '.join(artist_detail['genres'])
        
        if not track:
            cloudinary_img_url = upload_image_to_cloudinary(track_details['album']['images'][0]['url'])
            track = Track(
                spotify_id=spotify_id,
                name=track_details['name'],
                album_id=track_details['album']['id'],
                artists=','.join([artist['name'] for artist in track_details['artists']]),
                duration_ms=track_details['duration_ms'],
                popularity=track_details['popularity'],
                preview_url=track_details['preview_url'],
                release_date=track_details['album']['release_date'],
                album_name=track_details['album']['name'],
                album_release_date=track_details['album']['release_date'],
                cloudinary_img_url= cloudinary_img_url,
                track_genres = genres,
            )
            db.session.add(track)

        # Check if the track already exists in RecentTrack for the user
        existing_recent_track = RecentTrack.query.filter_by(user_id=user_id, spotify_id=spotify_id).first()
        if existing_recent_track:
            # Update the existing recent track's played_at timestamp
            existing_recent_track.played_at = played_at
        else:
            # Create a new RecentTrack entry
            new_recent_track = RecentTrack(
                user_id=user_id,
                track_id=track.id if track else None,
                played_at=played_at,
                spotify_id=spotify_id
            )
            db.session.add(new_recent_track)

        db.session.commit()
        return jsonify({'message': 'Recent track added successfully'}), 200
    else:
        return jsonify({'error': 'Failed to fetch track details from Spotify API'}), 400


@app.route('/personal/recent/tracks', methods=['GET'])
@jwt_required()
def get_recent_tracks():
    user_id = get_jwt_identity()
    
    # Join RecentTrack and Track tables to get necessary data
    recent_tracks_data = db.session.query(
        RecentTrack.played_at,
        Track.name,
        Track.cloudinary_img_url,
        Track.artists,
        Track.duration_ms,
        Track.id,
        RecentTrack.spotify_id
    ).join(
        RecentTrack.track
    ).filter(
        RecentTrack.user_id == user_id
    ).order_by(desc(RecentTrack.played_at)).limit(5)  # Order by played_at in ascending order

    if recent_tracks_data:
        serialized_data = []
        for track_data in recent_tracks_data:
            serialized_data.append({
                'played_at': track_data.played_at,
                'name': track_data.name,
                'spotify_image_url': track_data.cloudinary_img_url,
                'artists': track_data.artists.split(','), 
                'duration' : track_data.duration_ms,
                'id': track_data.id,
                'spotify_id': track_data.spotify_id
            })
        
        return jsonify({'recent_tracks': serialized_data}), 200
    else:
        return jsonify({'message': 'No recent tracks found'}), 404
    
@app.route('/personal/favourites/track', methods=['POST'])
@jwt_required()
def add_personal_favourites_tracks():
    try:
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        
        current_user_id = get_jwt_identity()
        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()

        if not user_pref:
            user_pref = UserPreference(user_id=current_user_id)
            db.session.add(user_pref)

        spotify_id = request.json.get('spotify_id')  # Assuming you're sending track URI in the request

        # Check if track already exists
        track = Track.query.filter_by(spotify_id=spotify_id).first()
        if not track:
            track_details = sp.track(spotify_id)
            artist_detail = sp.artist(track_details['artists'][0]['id'])
            genres = ', '.join(artist_detail['genres'])
            
            cloudinary_img_url = upload_image_to_cloudinary(track_details['album']['images'][0]['url'])
            track = Track(
                spotify_id=spotify_id,
                name=track_details['name'],
                album_id=track_details['album']['id'],
                artists=','.join([artist['name'] for artist in track_details['artists']]),
                duration_ms=track_details['duration_ms'],
                popularity=track_details['popularity'],
                preview_url=track_details['preview_url'],
                release_date=track_details['album']['release_date'],
                album_name=track_details['album']['name'],
                album_release_date=track_details['album']['release_date'],
                cloudinary_img_url=cloudinary_img_url,
                track_genres=genres,
            )
            db.session.add(track)
            db.session.commit()

        user_pref.favorite_tracks.append(track)
        db.session.commit()

        return jsonify({'message': 'Track added to favorites successfully'})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/personal/favourites/tracks', methods=['GET'])
@jwt_required()
def get_personal_favourites_tracks():
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
                'duration': track.duration_ms,
                'genres' : track.track_genres,
                'release_date': track.album_release_date,
                'spotify_image_url': track.cloudinary_img_url,
                'spotify_id' : track.spotify_id
            })
        return jsonify({'favourite_tracks': serialized_tracks})
    else:
        return jsonify({'message': 'No favorite tracks found'}), 404
    
@app.route('/personal/favourites/track', methods=['DELETE'])
@jwt_required()
def delete_personal_favourites_track():
    current_user_id = get_jwt_identity()
    track_id = request.json.get('spotify_id')
    user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
    if user_pref:
        track = Track.query.filter_by(spotify_id=track_id).first()
        if track:
            user_pref.favorite_tracks.remove(track)
            db.session.commit()
            return jsonify({'message': 'Track removed from favorites successfully'})
        else:
            return jsonify({'error': 'Track not found'}), 404
    else:
        return jsonify({'message': 'No favorite tracks found'}), 404
    
@app.route('/personal/favourites/track/check', methods=['POST'])
@jwt_required()
def check_favourite_track():
    current_user_id = get_jwt_identity()
    track_id = request.json.get('track_id')
    user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
    if user_pref:
        if track_id:
            is_favorite = any(track.id == track_id for track in user_pref.favorite_tracks)
            return jsonify({'favourite' : is_favorite})
        else:
            spotify_id = request.json.get('spotify_id')
            is_favorite = any(track.spotify_id == spotify_id for track in user_pref.favorite_tracks)
            return jsonify({'favourite' : is_favorite})
    else:
        return jsonify({'message': 'User preference not found'}), 404
    
@app.route('/personal/favourites/artist', methods=['POST'])
@jwt_required()
def add_personal_favourite_artist():
    current_user_id = get_jwt_identity()
    artist_id = request.json.get('artist_id')
    if artist_id is None:
        return jsonify({'message': 'Missing artist_id'}), 400

    user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
    if not user_pref:
        # Create a new UserPreference instance
        user_pref = UserPreference(user_id=current_user_id)
        db.session.add(user_pref)
        db.session.commit()

    artist = Artist.query.filter_by(spotify_id=artist_id).first()
    if not artist:
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        artist_data = sp.artist(artist_id)
        genres = ', '.join(artist_data['genres'])
        cloudinary_artist_image_url = upload_image_to_cloudinary(artist_data['images'][0]['url'])
        artist = Artist(
            spotify_id=artist_id,
            name=artist_data['name'],
            genres=genres,
            cloudinary_artist_image_url=cloudinary_artist_image_url,
            followers=artist_data['followers']['total']  # Set initial followers count
        )
        db.session.add(artist)
    else:
        artist.followers += 1

    user_pref.favorite_artists.append(artist)
    db.session.commit()
    return jsonify({'message': 'Artist added to favorites successfully'})

@app.route('/personal/favourites/artists', methods=['GET'])
@jwt_required()
def get_personal_favourite_artists():
    current_user_id = get_jwt_identity()
    user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
    if user_pref:
        favorite_artists = user_pref.favorite_artists
        serialized_artists = []
        for artist in favorite_artists:
            serialized_artists.append({
                'id': artist.id,
                'name': artist.name,
                'genres': artist.genres.split(','),
                'spotify_image_url': artist.cloudinary_artist_image_url,
                'artist_id': artist.spotify_id,
                'followers' : artist.followers
            })
        return jsonify({'favorite_artists': serialized_artists})
    else:
        return jsonify({'message': 'No favorite artists found'}), 404
    
@app.route('/personal/favourites/artist', methods=['DELETE'])
@jwt_required()
def delete_personal_favourites_artist():
    current_user_id = get_jwt_identity()
    artist_id = request.json.get('artist_id')
    user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
    if user_pref:
        artist = Artist.query.filter_by(spotify_id=artist_id).first()
        if artist:  
            # Decrement the followers count by 1
            if artist.followers > 0:
                artist.followers -= 1

            user_pref.favorite_artists.remove(artist)
            db.session.commit()
            return jsonify({'message': 'Artist removed from favorites successfully'})
        else:
            return jsonify({'error': 'Artist not found'}), 404
    else:
        return jsonify({'message': 'No favorite artists found'}), 404
    
@app.route('/personal/favourites/artist/check', methods=['POST'])
@jwt_required()
def check_favourite_artist():
    current_user_id = get_jwt_identity()
    artist_id = request.json.get('artist_id')
    user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
    if user_pref:
        if artist_id:
            is_favorite = any(artist.spotify_id == artist_id for artist in user_pref.favorite_artists)
            return jsonify({'favourite' : is_favorite})
        else:
            spotify_id = request.json.get('spotify_id')
            is_favorite = any(artist.spotify_id == spotify_id for artist in user_pref.favorite_artists)
            return jsonify({'favourite' : is_favorite})
    else:
        return jsonify({'message': 'User preference not found'}), 404
    
# ----------------- PLAYBACK ------------------------- # 
@app.route('/transfer-playback', methods=['POST'])
def transfer_playback():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Decode the token
    target_device_id = request.json.get('target_device_id')  # Get the target device ID from the request

    # Initialize Spotify client
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    try:
        # Transfer playback to the specified device
        sp.transfer_playback(device_id=target_device_id, force_play=True)
        return jsonify({'success': True, 'message': 'Playback transferred successfully.'}), 200
    except spotipy.SpotifyException as e:
        return jsonify({'success': False, 'message': str(e)}), 400
    
@app.route('/active-devices')
def get_active_devices():
    access_token = redis.get('spotify_access_token')
    
    if access_token is None:
        return jsonify({'message': 'Access token not found in Redis.'}), 404
    
    access_token = access_token.decode('utf-8')  # Decode the token
    
    # Initialize Spotify client
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
    # Retrieve user's active devices
    devices = sp.devices()
    active_devices = []
    for device in devices['devices']:
        if device['is_active']:
            active_devices.append({
                'id': device['id'],
                'name': device['name']
            })

    if not active_devices:
        return jsonify({'message': 'No active devices found.'}), 404
    
    return jsonify({'devices': active_devices})

@app.route('/playback/play', methods=['POST'])
@jwt_required()
def pyppo_play_track():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    track_uri = request.json.get('trackUri')
    device_id = request.json.get('myDeviceId')
    
    @retry(stop_max_attempt_number=3, wait_fixed=1000, retry_on_result=lambda result: result is False)
    def start_playback():
        try:
            sp.start_playback(device_id=device_id, uris=[track_uri])
            time.sleep(1)
            return True  # Success
        except spotipy.SpotifyException as e:
            if e.http_status == 404:  # No active device found
                print("No active device found. Retrying...")
                return False  # Retry
            else:
                raise  # Raise exception for other errors

    try:
        start_playback()
        return jsonify({'success': True, 'message': 'Playback started successfully.'}), 200
    except Exception as e:
        return jsonify({'success': False, 'message': 'Failed to start playback: ' + str(e)}), 500


# @socketio.on('playTrack')
# def pyppo_play_track_socketio(data):
#     access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
#     sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

#     track_uri = data['trackUri']
#     device_id = data['myDeviceId']

#     @retry(stop_max_attempt_number=3, wait_fixed=1000)
#     def start_playback():
#         sp.start_playback(device_id=device_id, uris=[track_uri])

#     try:
#         start_playback()
#         emit('trackStarted', {'current_track': track_uri})
#     except Exception as e:
#         print('Failed to start playback: ' + str(e))

@app.route('/playback/pause', methods=['POST'])
@jwt_required()
def pyppo_pause_track():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    device_id = request.json.get('myDeviceId')

    sp.pause_playback(device_id=device_id)
    
    return jsonify({'success': True, 'message': 'Playback paused successfully.'}), 200

@app.route('/playback/resume', methods=['POST'])
@jwt_required()
def resume_track():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    device_id = request.json.get('myDeviceId')

    sp.start_playback(device_id=device_id)
    
    return jsonify({'success': True, 'message': 'Playback resumed successfully.'}), 200

@app.route('/playback/next', methods=['POST'])
@jwt_required()
def next_track():
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
    
    return jsonify(response_data), 200

@app.route('/playback/previous', methods=['POST'])
@jwt_required()
def previous_track():
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
    
    return jsonify(response_data), 200

@app.route('/playback/shuffle', methods=['POST'])
@jwt_required()
def toggle_shuffle():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    device_id = request.json.get('myDeviceId')
    shuffle_state = request.json.get('shuffleState')  # True to enable shuffle, False to disable
    sp.shuffle(shuffle_state, device_id=device_id)
    return jsonify({'success': True, 'message': f'Shuffle {"enabled" if shuffle_state else "disabled"} successfully.'}), 200

@app.route('/playback/repeat', methods=['POST'])
@jwt_required()
def toggle_repeat():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    device_id = request.json.get('myDeviceId')
    repeat_state = request.json.get('repeatState')  # 'track', 'context', or 'off'
    sp.repeat(repeat_state, device_id=device_id)
    return jsonify({'success': True, 'message': f'Repeat mode set to {repeat_state} successfully.'}), 200

@app.route('/playback/seek', methods=['POST'])
@jwt_required()
def seek():
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

            return jsonify({'new_position': new_position_ms})
        else:
            return jsonify({'message': 'No track is currently playing'})
    else:
        print("Something wrong here")
        return jsonify({'message': 'Invalid new position'}), 400
    

@app.route('/playback/current_track_position')    
@jwt_required()
def spotify_current_track_position():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    # Get the current playback information
    playback_info = sp.current_playback()

    # Check if a track is currently playing
    if playback_info and playback_info['is_playing']:
        # Get the current track position
        current_track_position = playback_info['progress_ms']
    else:
        current_track_position = 0

    return jsonify({'current_track_position': current_track_position})

# def monitor_playback_status():
#     access_token = redis.get('spotify_access_token').decode('utf-8')
#     sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token);    
#     while True:
#         try:
#             # Retrieve current playback status
#             playback_state = sp.current_playback()
#             if playback_state is not None:
#                 is_playing = playback_state.get('is_playing', False)
#                 if not is_playing:
#                     # If playback is paused or stopped, pause playback
#                     sp.pause_playback()
#         except Exception as e:
#             print(f"Error monitoring playback status: {e}")
        
#         # Sleep for some time before checking again (e.g., 5 seconds)
#         time.sleep(5)

# # Start the background task
# monitor_thread = Thread(target=monitor_playback_status)
# monitor_thread.daemon = True
# monitor_thread.start()


# -------------------------------- GENRES --------------------------------#
@app.route('/genres')
def get_genres():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Decode the token
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
    genres = sp.recommendation_genre_seeds();
    
    return jsonify({'genres': genres})


def map_genres_to_cloudinary():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Decode the token
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
    try:
        # Fetch recommendation genre seeds from Spotify
        results = sp.recommendation_genre_seeds()
        genres = results.get('genres', [])

        # Select 1/6 of the genres randomly
        selected_genres = genres[:21]

        # # Prepare a list of 21 image URLs (for illustration purposes)
        image_urls = [
            "https://w.wallhaven.cc/full/mp/wallhaven-mpwv6m.jpg", # Acoustic
            "https://t4.ftcdn.net/jpg/05/86/74/11/360_F_586741137_iWeW0ZxOk4V8jckwq15e2B4Y4OBAiLrY.jpg", # Afrobeat
            "https://s3.amazonaws.com/allprograms/wp-content/uploads/2023/07/13143904/music_blog_artist_musician_concert_show_stage.jpg", #Alternative Rock
            "https://stability-images-upload.s3.amazonaws.com/v1_txt2img_5cab3348-013f-490c-a186-b39c8bfae9bd.png", # Alternative
            "https://gstatic.gvn360.com/2022/04/Comment-obtenir-plus-de-graines-dorees-dans-Elden-Ring.jpg", # Ambient
            "https://w.wallhaven.cc/full/pk/wallhaven-pkqdve.png", #Anime
            "https://cdnb.artstation.com/p/assets/images/images/043/963/973/large/jota-cravo-to-the-grave-3.jpg?1638752111", # Black Metal
            "https://www.greenlightbooking.com/wp-content/uploads/2018/06/lonesomefolktriobluegrassperformersoutside.jpg", # Bluegrass
            "https://media.tegna-media.com/assets/WATN/images/ec679d63-4cbb-4590-b753-090b91f5b7d6/ec679d63-4cbb-4590-b753-090b91f5b7d6_1140x641.jpg", # Blues
            "https://i.pinimg.com/736x/73/a0/43/73a043e6119fb6d026a17bf50b3a080d.jpg", # Bossa Nova
            "https://www.celebritycruises.com/blog/content/uploads/2021/09/what-is-brazil-known-for-christ-the-redeemer-aerial-hero.jpg", # Brazilian
            "https://blog.native-instruments.com/wp-content/uploads/2022/10/how-to-make-breakbeat-featured.jpg", # Breakbeat
            "https://routenote.com/blog/wp-content/uploads/2017/01/music-British-flag.jpg", # British
            "https://generasiantemp.files.wordpress.com/2021/03/cantopop-1-1.jpg?w=950", # Cantopop
            "https://i.pinimg.com/474x/06/6b/3a/066b3a74d3daf479c6edc7e93cf73a81.jpg", # Chicago House
            "https://www.childrens.com/wps/wcm/connect/childrenspublic/127c624b-8804-4e3b-8b83-a27fd8bb23bc/shutterstock_558144412_800x480.jpg?MOD=AJPERES&CVID=", # Children's Music
            "https://www.wearetheguard.com/sites/default/files/best-chill-music-week-01-2019.jpg", # Chill
            "https://img.apmcdn.org/c75e4ad850e43237fe0568a59ab71b15cb2511ac/uncropped/b80d45-20120627-flute-concert.jpg", # Classical
            "https://assets-global.website-files.com/65496b1500aed8ad52a5a193/654d8d74f8e0ef605d28b38c_745c24f2-480b-4cb1-8675-4840178a4c07_StageEffects.jpeg", # Club
            "https://i.ytimg.com/vi/L9PPPufTamE/maxresdefault.jpg", # Comedy
            "https://thesouthtexan.com/wp-content/uploads/2023/12/149232937_country-music.jpg", # Country
        ]
        
        genre_image_map = dict(zip(selected_genres, image_urls))
        cloudinary_genre_image_map = {genre: upload_genres_image_to_cloudinary(image_url, genre_key=genre) for genre, image_url in genre_image_map.items()}
        
        for genre_name, image_url in cloudinary_genre_image_map.items():
            genre = Genre(genre_name=genre_name, cloudinary_image_url=image_url)
            db.session.add(genre)

        db.session.commit()

        return jsonify({'message': 'Genre data inserted successfully'})
    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)}), 500


@app.route('/recommendation/genres')
def recommend_genres():
    genres = Genre.query.all()
    # Convert the list of Genre objects to a list of dictionaries
    genres_list = [{'id': genre.id, 'genre_name': genre.genre_name, 'genre_image': genre.cloudinary_image_url} for genre in genres]
    return jsonify({'genres': genres_list})

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

@app.route('/recommendation/genres/<path:genre_name>')
def recommend_genres_by_name(genre_name):
    access_token = redis.get('spotify_access_token').decode('utf-8') 
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            formatted_tracks = executor.submit(fetch_tracks_by_genre, sp, genre_name).result()
        return jsonify({'formatted_tracks': formatted_tracks})
    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})

def fetch_artists_by_genre(sp, genre):
    artists_info = sp.search(q=f'genre:"{genre}"', type='artist', limit=20)['artists']['items']
    formatted_artists = []
    for artist_info in artists_info:
        formatted_artist = {
            "name": artist_info["name"],
            "artist_id": artist_info["id"],
            "popularity": artist_info["popularity"],
            "spotify_image_url": artist_info["images"][0]["url"] if artist_info["images"] else None
        }
        formatted_artists.append(formatted_artist)
    sorted_artists = sorted(formatted_artists, key=lambda x: x['popularity'], reverse=True)[:6]
    return sorted_artists

@app.route('/recommendation/artists/<genre>')
@cache.cached(timeout=3600)  # Cache the result for 1 hour (3600 seconds)
def recommend_artists_by_genre(genre):
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth ,auth=access_token)

    try:
        sorted_artists = fetch_artists_by_genre(sp, genre)
        return jsonify({'sorted_artists': sorted_artists})
    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})
    

    
def fetch_tracks_by_specific_genre(sp, genre):
    results = sp.search(q=f'genre:"{genre}"', type='track', limit=12)
    tracks_info = results['tracks']['items']
    formatted_tracks = []
    for track_info in tracks_info:
        artists = ", ".join([artist['name'] for artist in track_info['artists']])
        album_info = track_info['album']
        album_images = album_info['images']
        album_image_url = album_images[0]['url'] if album_images else None
        formatted_track = {
            "name": track_info["name"],
            "artists": artists,
            "duration": track_info["duration_ms"],
            "spotify_id": track_info["id"],
            "popularity": track_info["popularity"],
            "spotify_image_url": album_image_url
        }
        formatted_tracks.append(formatted_track)
    sorted_tracks = sorted(formatted_tracks, key=lambda x: x['popularity'], reverse=True)[:6]
    return sorted_tracks

@app.route('/recommendation/tracks/<path:genre>')
@cache.cached(timeout=3600)  # Cache the result for 1 hour (3600 seconds)
def recommend_tracks_by_genre(genre):
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager= sp_oauth, auth=access_token)

    try:
        with concurrent.futures.ThreadPoolExecutor() as executor:
            sorted_tracks = executor.submit(fetch_tracks_by_specific_genre, sp, genre).result()
        return jsonify({'sorted_tracks': sorted_tracks})
    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})
    
# ------------------- ARTIST ------------------------ #
@app.route('/artist/<path:artist_id>')
def get_artist(artist_id):
    # Check if the artist is already in the database
    artist = Artist.query.filter_by(spotify_id=artist_id).first()

    if artist:
        # If the artist is found in the database, return the stored information
        return jsonify({
            'name': artist.name,
            'image': artist.cloudinary_artist_image_url,
            'genres': artist.genres,
            'followers': artist.followers
        })
    else:
        # If the artist is not found in the database, fetch the information from the Spotify API
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        
        artist_info = sp.artist(artist_id)
        artist_name = artist_info['name']
        artist_image = artist_info['images'][0]['url'] if artist_info['images'] else None
        artist_genres = artist_info['genres']
        artist_followers = artist_info['followers']['total']
        
        # Insert the artist information into the database
        new_artist = Artist(spotify_id=artist_id, name=artist_name, cloudinary_artist_image_url=upload_image_to_cloudinary(artist_image), genres=', '.join(artist_genres), followers=artist_followers)
        db.session.add(new_artist)
        db.session.commit()
        
        # Return the fetched information
        return jsonify({
            'name': artist_name,
            'image': artist_image,
            'genres': artist_genres,
            'followers': artist_followers
        })
        
def fetch_artist_top_tracks(sp, artist_ids):
    # Create a ThreadPoolExecutor
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # Use list comprehension to create a list of futures
        futures = [executor.submit(fetch_top_tracks_for_artist, sp, artist_id) for artist_id in artist_ids]

        # Gather the results as they become available
        tracks = []
        for future in concurrent.futures.as_completed(futures):
            tracks.extend(future.result())

    return jsonify(tracks)

def fetch_top_tracks_for_artist(sp, artist_id):
    # Create a new Spotify object inside this function
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
    top_tracks = sp.artist_top_tracks(artist_id)

    # Get artist name
    artist_info = sp.artist(artist_id)
    artist_name = artist_info['name']
    
    # Extract track information
    tracks = []
    for track in top_tracks['tracks']:
        tracks.append({
            "name": track["name"],
            "duration": track["duration_ms"],
            "spotify_id": track["id"],
            "popularity": track["popularity"],
            "spotify_image_url": track["album"]["images"][0]["url"],
            "artists": artist_name
        })

    # Return only the first 6 tracks
    return tracks[:6]

@app.route('/artist/<path:artist_id>/top-tracks')
@cache.cached(timeout=3600)  # Cache the result for 1 hour (3600 seconds)
def fetch_top_tracks(artist_id):
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    return jsonify(fetch_top_tracks_for_artist(sp, artist_id))  # Pass sp as an argument

    


# async def fetch_artists(session, genre):
#     access_token = redis.get('spotify_access_token').decode('utf-8')
#     headers = {'Authorization': f'Bearer {access_token}'}
#     url = f'https://api.spotify.com/v1/search?q=genre:"{genre}"&type=artist&limit=20'

#     async with session.get(url, headers=headers) as response:
#         data = await response.json()
#         artists = data.get('artists', {}).get('items', [])
#         formatted_artists = []

#         for artist in artists:
#             formatted_artist = {
#                 "name": artist.get("name", ""),
#                 "artist_id": artist.get("id", ""),
#                 "popularity": artist.get("popularity", 0),
#                 "image_url": artist.get("images", [{}])[0].get("url", "")  # Get the first image URL if available
#             }
#             formatted_artists.append(formatted_artist)

#         # Sort artists by popularity
#         sorted_artists = sorted(formatted_artists, key=lambda x: x['popularity'], reverse=True)

#         return "hello"

# async def fetch_and_cache_artists(genre):
#     artists = await fetch_artists(aiohttp.ClientSession(), genre)
#     redis.set(genre, json.dumps({'artists': artists}), ex=3600)  # Cache for 1 hour
#     return artists

# async def get_cached_artists(genre):
#     cached_data = redis.get(genre)
#     if cached_data:
#         return json.loads(cached_data.decode('utf-8'))
#     else:
#         artists = await fetch_and_cache_artists(genre)
#         return artists

# @app.route('/recommendation/artists/<genre>')
# async def recommend_artists(genre):
#     artists = await get_cached_artists(genre)
#     return jsonify(artists)

# --------------------------- PAYPAL PAYMENT ----------------------- #

@app.route('/paypal/payment/capture', methods=['POST'])
@jwt_required()
def paypal_capture():
    data = request.json
    user_id = get_jwt_identity()  # Get the user ID from the JWT

    # Extract the relevant information from the data
    transaction_id = data['id']
    amount = float(data['purchase_units'][0]['amount']['value'])
    currency = data['purchase_units'][0]['amount']['currency_code']
    status = data['status']
    email = data['payer']['email_address'] 
    
    payment = Payment(user_id, transaction_id, amount, currency, status, email)
    
    db.session.add(payment)
    db.session.commit()
    upgrade_to_premium(user_id)
    return jsonify({"payload" : data}), 200

# --------------------------- CALLBACK --------------------------- #    
@app.route('/callback')
def callback():
    code = request.args.get('code')
    if not code:
        return jsonify({'message': 'Authorization code is missing'}), 400
    else:
        # Call the get_access_token function with the authorization code
        return get_access_token(code)
    
@app.route('/authorization')
def authorization():
    return spotify_authorization()


def spotify_authorization():
    authorization_params = {
        'client_id': sp_oauth.client_id,
        'response_type': 'code',
        'redirect_uri': sp_oauth.redirect_uri,
        'scope': sp_oauth.scope,
    }

    # Create the authorization URL
    authorization_url = "https://accounts.spotify.com/authorize?" + urlencode(authorization_params)

    # Redirect the user to the Spotify login page
    return redirect(authorization_url)

spotify_authorization()

def get_access_token(code):    
    if not code:
        return jsonify({'error': 'Authorization code is missing'}), 400

    token_url = 'https://accounts.spotify.com/api/token'

    # Encode client_id and client_secret to Base64
    client_credentials = f"{sp_oauth.client_id}:{sp_oauth.client_secret}"
    base64_credentials = b64encode(client_credentials.encode()).decode()

    # Prepare the request body
    token_params = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': sp_oauth.redirect_uri
    }

    # Prepare the request headers
    headers = {
        'Authorization': f"Basic {base64_credentials}",
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    try:
        # Make a POST request to the Spotify API
        response = requests.post(token_url, data=token_params, headers=headers)
        response.raise_for_status()  # Check for HTTP errors
        
        token_info = response.json()
        
        # Check if 'access_token' exists in token_info
        if 'access_token' in token_info:
            redis.set('spotify_access_token', token_info['access_token'])
            redis.set('spotify_refresh_token', token_info['refresh_token'])           
        return jsonify(token_info)
    except requests.exceptions.RequestException as e:
        return jsonify({'error': str(e)}), 500  # Return an error response

# ----------------------- LOGIN - REGISTER ------------------------ #
@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username')
    password = request.json.get('password')

    if not username or not password:
        return jsonify({'error': 'Username and password required'}), 400

    user = User.query.filter_by(username=username).first()

    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'error': 'Invalid username or password'}), 401

    # Check if a refresh token exists for the user
    existing_refresh_token = RefreshToken.query.filter_by(user_id=user.id).first()

    if existing_refresh_token:
        # Use existing refresh token
        refresh_token = existing_refresh_token.jti
    else:
        # Create a new refresh token
        refresh_token = create_refresh_token(identity=user.id)
        # Save the new refresh token to the database
        insert_refresh_token(refresh_token, user.id)

    # Create a new access token with a 3-day expiry time
    access_token = create_access_token(identity=user.id, expires_delta=timedelta(days=3))
    
    profile = {
        'username': user.username,
        'email': user.email,
        'role': user.role
    }

    response = jsonify({'profile': profile, 'login': True, 'access_token': access_token, 'refresh_token': refresh_token, 'spotify_token' : redis.get('spotify_access_token').decode('utf-8')})
    set_access_cookies(response, access_token)
    set_refresh_cookies(response, refresh_token)
    
    return response, 200


@app.route('/check-auth', methods=['GET'])
def check_auth():
    try:
        verify_jwt_in_request()
        return jsonify({'isAuthenticated': True}), 200
    except:
        return jsonify({'isAuthenticated': False}), 401


@app.route('/register', methods=['POST'])
def register():
    
    data = request.json
    username = data.get('username')
    email = data.get('email')
    password = data.get('password')

    # Check if the user already exists
    existing_user = User.query.filter_by(username=username).first()

    if existing_user:
        return jsonify({'message': 'Username already exists'}), 400

    # Create a new user
    new_user = User(username=username, email=email, password=password)
    db.session.add(new_user)
    db.session.commit()
    return jsonify({'message': 'Registration successful'}), 201

@app.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    # Get the current user's ID
    current_user_id = get_jwt_identity()

    # Get the JTI of the current refresh token
    current_jti = get_jwt()["jti"]

    # Check if the refresh token is in the database and not revoked
    token_in_db = RefreshToken.query.filter_by(user_id=current_user_id, jti=current_jti, revoked=False).first()
    if token_in_db is None:
        return {"msg": "Refresh token not found in database"}, 401

    # Create a new access token
    new_access_token = create_access_token(identity=current_user_id)
    refresh_token = token_in_db.token

    # Return the new access token and the refresh token
    return {"access_token": new_access_token, "refresh_token": refresh_token}, 200

def refresh_spotify_token():
    
    refresh_token = redis.get('spotify_refresh_token').decode('utf-8')
    if not refresh_token:
        return jsonify({'error': 'Refresh token is missing'}), 400

    # Your Spotify app's client ID and client secret
    client_id = sp_oauth.client_id  # Replace with your client ID
    client_secret = sp_oauth.client_secret  # Replace with your client secret

    # Prepare the headers
    credentials = f'{client_id}:{client_secret}'
    encoded_credentials = b64encode(credentials.encode('utf-8')).decode('utf-8')
    headers = {
        'Authorization': f'Basic {encoded_credentials}',
        'Content-Type': 'application/x-www-form-urlencoded'
    }

    body = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token
    }

    # Make a POST request to the Spotify API
    response = requests.post('https://accounts.spotify.com/api/token', headers=headers, data=body)
    response.raise_for_status()  # Raise an exception if the request failed

    # Store the new access token and its expiration time in Redis
    token_info = response.json()
    redis.set('spotify_access_token', token_info['access_token'])
    expires_at = int(time.time()) + token_info['expires_in']
    redis.set('expires_at', expires_at)

    socketio.emit('spotify_token_refreshed', {'spotify_access_token': token_info['access_token']})

    print("Token has been refreshed")
        
def check_token():
    if int(time.time()) > int(redis.get('expires_at') or 0) - 300:
        refresh_spotify_token()
        print("Token will expire in 5 minutes, force refresh now")
    

# Route for refreshing Spotify token
@app.route('/spotify/refresh', methods=['POST'])
def spotify_refresh():
    refresh_spotify_token()
    return jsonify({'message': 'Access token refreshed successfully'}), 200

@app.route('/profile', methods=['GET'])
@jwt_required()
def get_user_profile():
    current_user_id = get_jwt_identity()
    user = db.session.get(User, current_user_id)
    if not user:
        return jsonify({'message': 'User not found'}), 404
    profile_data = {
        'id': current_user_id,
        'username': user.username,
        'role' : user.role,
    }
    return jsonify({"profile" : profile_data}), 200


@app.route('/logout')
@jwt_required()
def logout():
    # Create the response object
    response = make_response(jsonify({'message': 'User logged out'}))
    unset_jwt_cookies(response)
    return response, 200

#----------------- EXTERNAL FUNCTION ---------------------------------#
def upload_image_to_cloudinary(image_url):
    try:
        # Upload image to Cloudinary
        response = cloudinary.uploader.upload(image_url)
        return response['secure_url']  # Return the Cloudinary image URL
    except Exception as e:
        print(f"Error uploading image to Cloudinary: {e}")
        return None
    
def upload_genres_image_to_cloudinary(image_url, genre_key):
    try:
        # Upload image to Cloudinary
        response = cloudinary.uploader.upload(image_url, public_id=genre_key)
        return response['secure_url']  # Return the Cloudinary image URL
    except Exception as e:
        print(f"Error uploading image to Cloudinary: {e}")
        return None
    
def send_email(sender_email, sender_password, recipient_email, subject, template_name, **template_vars):
    try:
        # SMTP Configuration
        smtp_server = 'smtp.gmail.com'
        smtp_port = 587

        # Create SMTP object
        server = smtplib.SMTP(smtp_server, smtp_port)
        server.starttls()  # Start TLS encryption
        server.login(sender_email, sender_password)

        # Create message
        msg = MIMEMultipart()
        msg['From'] = 'Pyppo The Final'
        msg['To'] = recipient_email
        msg['Subject'] = subject

        # Render HTML template
        html_content = render_template(template_name, **template_vars)

        # Attach HTML content
        msg.attach(MIMEText(html_content, 'html'))

        # Send email
        server.sendmail(sender_email, recipient_email, msg.as_string())
        print("Email sent successfully!")
        server.quit()

    except smtplib.SMTPAuthenticationError as e:
        print("SMTP Authentication Error:", e)
        print("Check if username and password are correct.")
        print("Also, ensure that you're not using 2-step verification.")
    except Exception as e:
        print("An error occurred:", e)
        print("Please check your SMTP server settings and try again.")

subject = 'Test Email'
message = 'This is a test email sent using Python.'

def upgrade_to_premium(user_id):
    user = User.query.get(user_id)
    user.role = 'premium'
    db.session.commit()
    return jsonify({'message': 'User upgraded to premium successfully'}), 200
    
@app.route('/send-mail')
def send_thanks_mail():
    send_email('dennisofcetus98@gmail.com', 'yuqm gfyd zdmi pjmg', 'delta06coder@gmail.com', subject=subject, template_name='thank_mail.html', name='John', age=30)
    return "Email sent successfully"

scheduler = BackgroundScheduler()
scheduler.start()
scheduler.add_job(
    func=check_token,
    trigger=IntervalTrigger(seconds=30),  # Check the token every minute
    id='check_token_job',
    name='Check if the Spotify token needs to be refreshed',
    replace_existing=True)
atexit.register(lambda: scheduler.shutdown())

# -------------- HEATH CHECK -----------------# 
@app.route('/healthcheck', methods=['GET'])
def healthcheck():
    try:
        # Try to query the database
        db.session.query("1").from_statement("SELECT 1").all()
        return jsonify({"status": "OK"}), 200
    except Exception as e:
        # If an error occurred, return a 500 status code and the error message
        return jsonify({"status": "Error", "message": str(e)}), 500
    
# @app.route('/api')
# def redirect_to_swagger():
#     return redirect(url_for('index'))

if __name__ == '__main__':
    spotify_authorization()
    socketio.run(app, debug=True, port=5002)