from flask import Flask, request, jsonify, make_response, current_app, redirect, session, url_for
from flask_cors import CORS
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_jwt_extended import create_access_token, JWTManager, jwt_required, get_jwt_identity, unset_jwt_cookies, create_refresh_token
from flask_session import Session
import random


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
from database import db

import asyncio
import aiohttp

from apscheduler.schedulers.background import BackgroundScheduler

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
#End import werkzeug

from flask_redis import FlaskRedis

import base64
import requests
from urllib.parse import urlencode
from base64 import b64encode
from datetime import datetime
import time
import json
from threading import Thread


app = Flask(__name__, instance_relative_config=True)
app.secret_key = 'Delta1006'


login_manager = LoginManager(app)
login_manager.init_app(app)

CORS(app, origins=["http://localhost:3000"])  # Replace with your frontend URL
redis = FlaskRedis(app)
jwt = JWTManager(app)
jwt.init_app(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:Delta1006@127.0.0.1/pyppo'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['JWT_SECRET_KEY'] = app.secret_key
app.config['SECRET_KEY'] = app.secret_key
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False  # Ensure session is not permanent
app.config['REDIS_URL'] = "redis://:Delta1006@localhost:6379/0"
# End configuring SQLAlchemy Database


db.init_app(app)
migrate = Migrate(app, db)

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
    scope = 'user-library-read user-library-modify user-top-read app-remote-control streaming user-read-playback-state user-modify-playback-state user-read-currently-playing playlist-modify-public user-read-private user-read-email playlist-read-private'

)

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
def get_pyppo_dashboard():
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    
    
    # Must return data of track recommendation , limit 10
    
    # Must return data of track based on same "type"
    
    
    try:
        # Fetching user's playlists
        user_playlists_results = sp.current_user_playlists()
        
        something = sp.search(q='jkve', limit=20)
        
        user_playlists = user_playlists_results.get('items', [])

        # Extract relevant information from each playlist
        playlists_info = []
        for playlist in user_playlists:
            playlist_info = {
                'name': playlist.get('name', 'Unknown Playlist'),
                'uri': playlist.get('uri', ''),
                'tracks': []
            }

            # Fetch tracks within the playlist
            playlist_tracks_results = sp.playlist_tracks(playlist['id'], limit=10)
            playlist_tracks = playlist_tracks_results.get('items', [])

            # Extract relevant information from each track in the playlist
            for track in playlist_tracks:
                track_info = {
                    'name': track.get('track', {}).get('name', 'Unknown Track'),
                    'artist': track.get('track', {}).get('artists', [{}])[0].get('name', 'Unknown Artist'),
                    'uri': track.get('track', {}).get('uri', '')
                }
                playlist_info['tracks'].append(track_info)

            playlists_info.append(playlist_info)
            
            playlist_info = list(set(playlists_info))

        return jsonify({'user_playlists': playlists_info, 'search' : something})

    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})


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
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Decode the token
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)  
    search_query = request.args.get('query')

    try:
        # Search for tracks in the database
        database_tracks = Track.query.filter(Track.name.ilike(f'%{search_query}%')).limit(10).all()
        track_info = []

        # Process tracks from the database
        for track in database_tracks:
            track_info.append({
                'id': track.id,
                'spotify_id': track.spotify_id,
                'name': track.name,
                'artists': track.artists,
                'duration' : track.duration_ms,
                'spotify_image_url': track.cloudinary_img_url  # Include Spotify image URL
            })
            
        # Check if there are enough tracks in the database
        if len(track_info) < 5:
            # Determine how many additional tracks are needed
            remaining_tracks_count = 5 - len(track_info)

            # Search for additional tracks using the Spotify API
            spotify_results = sp.search(q=search_query, type='track', limit=remaining_tracks_count)
            tracks_from_spotify = spotify_results.get('tracks', {}).get('items', [])

            # Extract relevant information from each track and add it to the response
            for track in tracks_from_spotify:
                # Add track information to the response
                track_info.append({
                    'id' : tracks_from_spotify.index(track) + 1,
                    'spotify_id': track['id'],
                    'name': track['name'],
                    'artists': track['artists'][0]['name'],
                    'duration': track['duration_ms'],
                    'spotify_image_url': track['album']['images'][0]['url']  # Get image URL from Spotify
                })

        return jsonify({'search_results': track_info})

    except spotipy.SpotifyException as e:
        # Handle Spotify API errors
        return jsonify({'error': str(e)}), 500

# ------------------------ PERSONAL PLAYLISTS -------------------------- #
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
                    # Add more track details as needed
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
                'cloudinary_img_url': track_data.cloudinary_img_url,
                'artists': track_data.artists.split(','), 
                'spotify_id': track_data.spotify_id
            })
        
        return jsonify({'recent_tracks': serialized_data}), 200
    else:
        return jsonify({'message': 'No recent tracks found'}), 404
    
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
def pyppo_play_track():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    track_uri = request.json.get('trackUri')
    device_id = request.json.get('deviceId')

    sp.start_playback(device_id=device_id, uris=[track_uri])
    
    return jsonify({'success': True, 'message': 'Playback started successfully.'}), 200

@app.route('/playback/pause', methods=['POST'])
def pyppo_pause_track():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    device_id = request.json.get('deviceId')

    sp.pause_playback(device_id=device_id)
    
    return jsonify({'success': True, 'message': 'Playback paused successfully.'}), 200

@app.route('/playback/resume', methods=['POST'])
def resume_track():
    access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

    device_id = request.json.get('deviceId')

    sp.start_playback(device_id=device_id)
    
    return jsonify({'success': True, 'message': 'Playback resumed successfully.'}), 200

@app.route('/playback/next', methods=['POST'])
def next_track():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    device_id = request.json.get('deviceId')

    playlists = sp.featured_playlists(limit=50)['playlists']['items']
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
            'artist' : current_track_info['track'].get('artists')[0].get('name'),
            'spotify_img_url' : current_track_info['track'].get('album').get('images')[0].get('url'),
            'duration' : current_track_info['track'].get('duration_ms')
        }
    }
    
    sp.start_playback(device_id=device_id, uris=[current_track_info['track'].get('uri')])
    
    return jsonify(response_data), 200

@app.route('/playback/previous', methods=['POST'])
def previous_track():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    device_id = request.json.get('deviceId')

    playlists = sp.featured_playlists(limit=50)['playlists']['items']
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
            'artist' : current_track_info['track'].get('artists')[0].get('name'),
            'spotify_img_url' : current_track_info['track'].get('album').get('images')[0].get('url'),
            'duration' : current_track_info['track'].get('duration_ms')
        }
    }
    
    sp.start_playback(device_id=device_id, uris=[current_track_info['track'].get('uri')])
    
    return jsonify(response_data), 200

@app.route('/playback/shuffle', methods=['POST'])
def toggle_shuffle():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    device_id = request.json.get('deviceId')
    shuffle_state = request.json.get('shuffleState')  # True to enable shuffle, False to disable
    sp.shuffle(shuffle_state, device_id=device_id)
    return jsonify({'success': True, 'message': f'Shuffle {"enabled" if shuffle_state else "disabled"} successfully.'}), 200

@app.route('/playback/repeat', methods=['POST'])
def toggle_repeat():
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    device_id = request.json.get('deviceId')
    repeat_state = request.json.get('repeatState')  # 'track', 'context', or 'off'
    sp.repeat(repeat_state, device_id=device_id)
    return jsonify({'success': True, 'message': f'Repeat mode set to {repeat_state} successfully.'}), 200

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

@app.route('/playlists/<path:playlist_id>')
def get_pyppo_playlists_by_id(playlist_id):
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    
    try:
        # Get playlist information using the Spotify API
        playlist_info = sp.playlist(playlist_id)

        # Extract relevant information from the playlist_info dictionary
        playlist_response = {
            'name': playlist_info['name'],
            'owner': playlist_info['owner']['display_name'],
            'uri': playlist_info['uri'],
            'image_url': playlist_info['images'][0]['url'] if 'images' in playlist_info else None,
            'tracks': []
        }

        # Fetch detailed information for each track in the playlist
        for track in playlist_info['tracks']['items']:
            track_info = track['track']
            playlist_response['tracks'].append({
                'name': track_info['name'],
                'uri': track_info['uri'],
                'duration_ms': track_info['duration_ms'],
                'preview_url': track_info['preview_url'],
                'artists': [{'name': artist['name'], 'uri': artist['uri']} for artist in track_info['artists']],
                'album': {'name': track_info['album']['name'], 'uri': track_info['album']['uri']}
            })

        return jsonify(playlist_response)

    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})
    
# --------------------------- ARTISTS --------------------------- #
@app.route('/artists/<path:artist_id>')
def get_pyppo_artists_id(artist_id):
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    
    try:
        # Get artist information using the Spotify API
        artist_info = sp.artist(artist_id)

        # Extract relevant information from the artist_info dictionary
        artist_response = {
            'name': artist_info['name'],
            'uri': artist_info['uri'],
            'followers': artist_info['followers']['total'],
            'genres': artist_info['genres'],
            'image_url': artist_info['images'][0]['url'] if 'images' in artist_info else None,
            'popularity': artist_info['popularity']
        }

        return jsonify(artist_response)

    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})
    
@app.route('/artists/<path:artist_id>/top-tracks')
def get_pyppo_top_tracks_of_artist(artist_id):
    sp = spotipy.Spotify(auth_manager=sp_oauth)

    try:
        # Get top tracks of the artist using the Spotify API
        top_tracks = sp.artist_top_tracks(artist_id, country='US')  # You can specify the country code as needed

        # Extract relevant information from the top_tracks dictionary
        tracks_response = []
        for track in top_tracks['tracks']:
            track_response = {
                'name': track['name'],
                'uri': track['uri'],
                'duration_ms': track['duration_ms'],
                'preview_url': track['preview_url'],
                'artists': [{'name': artist['name'], 'uri': artist['uri']} for artist in track['artists']],
                'album': {'name': track['album']['name'], 'uri': track['album']['uri']},
                'popularity': track['popularity']
            }
            tracks_response.append(track_response)

        return jsonify({'top_tracks': tracks_response})

    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})
    
@app.route('/artists/<path:artist_id>/related-artists')
def get_related_artists(artist_id):
    sp = spotipy.Spotify(auth_manager=sp_oauth)

    try:
        # Get related artists using the Spotify API
        related_artists = sp.artist_related_artists(artist_id)

        # Extract relevant information from the related_artists dictionary
        artists_response = []
        for related_artist in related_artists['artists']:
            artist_response = {
                'name': related_artist['name'],
                'uri': related_artist['uri'],
                'genres': related_artist['genres'],
                'image_url': related_artist['images'][0]['url'] if 'images' in related_artist else None,
                'popularity': related_artist['popularity']
            }
            artists_response.append(artist_response)

        return jsonify({'related_artists': artists_response})

    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})

# -------------------------------- ALBUMS -------------------------------- # 
@app.route('/albums/<path:album_id>')
def get_pyppo_album_by_id(album_id):
    sp = spotipy.Spotify(auth_manager=sp_oauth)

    try:
        # Get album information using the Spotify API
        album_info = sp.album(album_id)

        # Extract relevant information from the album_info dictionary
        response = {
            'name': album_info['name'],
            'artist': album_info['artists'][0]['name'],
            'release_date': album_info['release_date'],
            'uri': album_info['uri'],
            'image_url': album_info['images'][0]['url'] if 'images' in album_info else None,
            'tracks': [{'name': track['name'],
                        'uri': track['uri'],
                        'id' : track['id'],
                        'image_url': sp.track(track['id'])['album']['images'][0]['url'] if 'images' in sp.track(track['id'])['album'] else None} for track in album_info['tracks']['items']]
        }

        return jsonify(response)

    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})
    
@app.route('/albums/<path:album_id>/tracks')
def get_pyppo_albums_tracks(album_id): 
    sp = spotipy.Spotify(auth_manager=sp_oauth)
    
    try:
        # Get album information using the Spotify API
        album_info = sp.album(album_id)

        # Extract relevant information from the album_info dictionary
        album_response = {
            'name': album_info['name'],
            'artist': album_info['artists'][0]['name'],
            'release_date': album_info['release_date'],
            'uri': album_info['uri'],
            'image_url': album_info['images'][0]['url'] if 'images' in album_info else None,
            'tracks': []
        }

        # Fetch detailed information for each track in the album
        for track in album_info['tracks']['items']:
            track_info = sp.track(track['id'])
            album_response['tracks'].append({
                'name': track_info['name'],
                'uri': track_info['uri'],
                'duration_ms': track_info['duration_ms'],
                'preview_url': track_info['preview_url'],
                'artists': [{'name': artist['name'], 'uri': artist['uri']} for artist in track_info['artists']],
                'album': {'name': track_info['album']['name'], 'uri': track_info['album']['uri']}
            })

        return jsonify(album_response)

    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})



# -------------------------------- GENRES --------------------------------#
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


@app.route('/recommendation/genres/<path:genre_name>')
def recommend_genres_by_name(genre_name):
    access_token = redis.get('spotify_access_token').decode('utf-8') 
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
    formatted_tracks = []

    # Get tracks for the specified genre
    tracks_info = sp.recommendations(seed_genres=[genre_name], limit=30)['tracks']
    for track_info in tracks_info:
        formatted_track = {
            "name": track_info["name"],
            "track_id": track_info["id"],
            "album_id": track_info["album"]["id"],
            "artists": [artist["name"] for artist in track_info["artists"]],
            "duration_ms": track_info["duration_ms"],
            "popularity": track_info["popularity"],
            "preview_url": track_info["preview_url"],
            "release_date": track_info["album"]["release_date"],
            "album_name": track_info["album"]["name"],
            "image_url": track_info["album"]["images"][0]["url"]  # Assuming the first image is the main one
        }
        formatted_tracks.append(formatted_track)

    return jsonify({'formatted_tracks': formatted_tracks})

@app.route('/recommendation/artists/<genre>')
async def recommend_artists_by_genre(genre):
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
    try:
        # Get artists for the specified genre
        artists_info = sp.search(q=f'genre:"{genre}"', type='artist', limit=20)['artists']['items']
        formatted_artists = []
        for artist_info in artists_info:
            formatted_artist = {
                "name": artist_info["name"],
                "artist_id": artist_info["id"],
                "popularity": artist_info["popularity"],
                "image_url": artist_info["images"][0]["url"] if artist_info["images"] else None
            }
            formatted_artists.append(formatted_artist)
        sorted_artists = sorted(formatted_artists, key=lambda x: x['popularity'], reverse=True)[:6]
        return jsonify({'sorted_artists': sorted_artists})  # Corrected line
    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})
    
@app.route('/recommendation/tracks/<path:genre>')
def recommend_tracks_by_genre(genre):
    access_token = redis.get('spotify_access_token').decode('utf-8')
    sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
    
    try:
        # Get tracks for the specified genre
        results = sp.search(q=f'genre:"{genre}"', type='track', limit=12)
        tracks_info = results['tracks']['items']
        formatted_tracks = []
        for track_info in tracks_info:
            artists = ", ".join([artist['name'] for artist in track_info['artists']])
            album_info = track_info['album']
            album_images = album_info['images']
            album_image_url = album_images[0]['url'] if album_images else None  # Get the first image URL if available
            formatted_track = {
                "track_name": track_info["name"],
                "artists": artists,
                "track_id": track_info["id"],
                "popularity": track_info["popularity"],
                "image_url": album_image_url  # Use album image as a representation of the track
            }
            formatted_tracks.append(formatted_track)
        sorted_tracks = sorted(formatted_tracks, key=lambda x: x['popularity'], reverse=True)[:6]
        return jsonify({'sorted_tracks': sorted_tracks})
    except spotipy.SpotifyException as e:
        return jsonify({'error': str(e)})


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
    data = request.json
    username = data.get('username')
    password = data.get('password')

    # Query the database for the user
    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'message': 'Invalid username or password'}), 401
    
    
    access_token = create_access_token(identity=user.id)
    
    spotify_access_token_bytes = redis.get('spotify_access_token') or b''
    spotify_access_token = spotify_access_token_bytes.decode('utf-8')
    
    refresh_token = create_refresh_token(identity=user.id)
    insert_refresh_token(refresh_token, user.id)

    profile_data = {
        'user_id': user.id,
        'username': user.username,
        'email': user.email,
        'role': user.role,  
    }
    resp = make_response(jsonify({
        'message': 'Login successful',
        'profile': profile_data,
        'access_token': access_token,
        'spotify_access_token': spotify_access_token  # Include Spotify access token
    }))
    resp.set_cookie('access_token_cookie', value=access_token, httponly=True)
    
    return resp, 200


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
def refresh():
    refresh_spotify_token()
    return jsonify({'message': 'Access token refreshed successfully'}), 200

def refresh_spotify_token():
    
    if int(time.time()) < int(redis.get('expires_at') or 0):
        print("Token is still valid!")
    else:
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

        print("Token has been refreshed")
    

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
        'username': user.username,
        'email': user.email,
        'role' : user.role,
    }
    return jsonify(profile_data), 200


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


scheduler = BackgroundScheduler()
scheduler.add_job(refresh_spotify_token, 'interval', minutes=1)
scheduler.start()

if __name__ == '__main__':
    spotify_authorization()
    app.run(debug=True)