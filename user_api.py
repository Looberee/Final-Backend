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
from flask_restx import Api, Resource, fields, reqparse
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

authorizations = {
    'Bearer Auth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization'
    }
}


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
api = Api(app, doc='/api', version='1.0', title='Pyppo Web Music API', description='', authorizations=authorizations)

@app.route('/')
def index():
    return jsonify({"status": "success", "message": "Welcome to Pyppo Web Music API"}), 200

# ------------------- NAMESPACE -----------------------------
personal_ns = api.namespace('personal', description='Personal playlists operations')
authorize_ns = api.namespace('authorize', description='Authorization operations')
playback_ns = api.namespace('playback', description='Playback operations')
profile_ns = api.namespace('profile', description='Profile operations')
heathcheck_ns = api.namespace('heathcheck', description='Health check operations')
artists_ns = api.namespace('artists', description='Artists operations')
payment_ns = api.namespace('payment', description='Payment operations')
extra_ns = api.namespace('extra', description='Extra operations')
# ------------------- MODELS -----------------------------
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


edit_playlist_parser = reqparse.RequestParser()
edit_playlist_parser.add_argument('encode_id', type=str, required=True, help='Encode ID cannot be blank')
edit_playlist_parser.add_argument('new_name', type=str, required=True, help='New name cannot be blank')
delete_parser = reqparse.RequestParser()
delete_parser.add_argument('encode_id', type=str, required=True, help='Encode ID cannot be blank')

@personal_ns.route('/playlists')
class PersonalPlaylists(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @api.marshal_with(playlist_model, envelope='user_playlists')
    def get(self):
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
    @api.response(201, 'Playlist created successfully', playlist_model)
    def post(self):
        current_user_id = get_jwt_identity()
        user_playlists_count = UserPlaylist.query.filter_by(user_id=current_user_id).count()
        playlist_name = f'My playlist # {user_playlists_count + 1}'
        user_id = current_user_id
        new_playlist = UserPlaylist(name=playlist_name, user_id=user_id)
        db.session.add(new_playlist)
        db.session.commit()
        return {'message': 'Playlist created successfully', 'playlist_name': playlist_name}, 201

    @api.doc(security='apikey')
    @jwt_required()
    @api.expect(edit_playlist_parser)
    @api.response(204, 'Playlist updated successfully')
    def put(self):
        args = edit_playlist_parser.parse_args()
        encode_id = args.get('encode_id')
        new_name = args.get('new_name')

        # Find the playlist by ID
        playlist = UserPlaylist.query.filter_by(encode_id=encode_id).first()
        if playlist:
            current_user_id = get_jwt_identity()
            if playlist.user_id == current_user_id:  # Check if the playlist belongs to the current user
                playlist.name = new_name
                # Commit the changes to the database
                db.session.commit()
                return {'message': 'Playlist name updated successfully'}, 204
            else:
                return {'error': 'Unauthorized'}, 401
        else:
            return {'error': 'Playlist not found'}, 404

    @api.doc(security='apikey')
    @jwt_required()
    @api.expect(delete_parser)
    @api.response(204, 'Playlist deleted successfully')
    def delete(self):
        args = delete_parser.parse_args()
        encode_id = args.get('encode_id')

        # Find the playlist by ID
        playlist = UserPlaylist.query.filter_by(encode_id=encode_id).first()
        if playlist:
            current_user_id = get_jwt_identity()
            if playlist.user_id == current_user_id:  # Check if the playlist belongs to the current user
                # Delete the playlist
                db.session.delete(playlist)
                db.session.commit()
                return {'message': 'Playlist deleted successfully'}, 204
            else:
                return {'error': 'Unauthorized'}, 401
        else:
            return {'error': 'Playlist not found'}, 404
    
@personal_ns.route('/playlists/<string:encode_id>/tracks')
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
        
add_track_parser = reqparse.RequestParser()
add_track_parser.add_argument('playlist_id', type=str, required=True, help='Playlist ID is required')
add_track_parser.add_argument('track_id', type=str, required=True, help='Track ID is required')

@personal_ns.route('/playlists/<string:playlist_id>/track/<string:track_id>')
class PersonalPlaylistTrack(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    def post(self, playlist_id, track_id):
        current_user_id = get_jwt_identity()
        playlist = UserPlaylist.query.filter_by(encode_id=playlist_id, user_id=current_user_id).first()
        if playlist:
            # Check if the track exists in the Track model
            track = Track.query.filter_by(spotify_id=track_id).first()
            if track:
                existing_track = UserPlaylistTrack.query.filter_by(user_playlist_id=playlist.id, track_id=track.id).first()
                if existing_track:
                    return {'error': 'Track already exists in the playlist'}, 400

                # Track exists, add it to the user's playlist
                new_playlist_track = UserPlaylistTrack(user_playlist_id=playlist.id, track_id=track.id)
                db.session.add(new_playlist_track)
                db.session.commit()
                return {'message': 'Track added to the playlist successfully'}, 201
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
                    
                    return {'message': 'Track added to the playlist successfully'}, 201
                else:
                    return {'error': 'Failed to fetch track data from Spotify API'}, 500
        else:
            return {'error': 'Playlist not found'}, 404

    @api.doc(security='apikey')
    @jwt_required()
    def delete(self, playlist_id, track_id):
        current_user_id = get_jwt_identity()
        playlist = UserPlaylist.query.filter_by(encode_id=playlist_id, user_id=current_user_id).first()

        if playlist:
            track = Track.query.filter_by(spotify_id=track_id).first()
            if track:
                playlist_track = UserPlaylistTrack.query.filter_by(user_playlist_id=playlist.id, track_id=track.id).first()
                if playlist_track:
                    db.session.delete(playlist_track)
                    db.session.commit()
                    return {'message': 'Track removed from the playlist successfully'}, 204
                else:
                    return {'error': 'Track not found in the playlist'}, 404
            else:
                return {'error': 'Track not found'}, 404
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

add_artist_parser = reqparse.RequestParser()
add_artist_parser.add_argument('artist_id', type=str, required=True, help='Artist ID')
delete_artist_parser = reqparse.RequestParser()
delete_artist_parser.add_argument('artist_id', type=str, required=True, help='Artist ID')

@favourites_ns.route('/artists')
class PersonalFavoriteArtists(Resource):
    @favourites_ns.doc(security='apikey')
    @jwt_required()
    @favourites_ns.marshal_with(artist_model, envelope='favourite_artists')
    def get(self):
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
            return serialized_artists, 200
        else:
            return {'message': 'No favourite artists found'}, 200

    @favourites_ns.doc(security='apikey')
    @jwt_required()
    @favourites_ns.expect(add_artist_parser, validate=True)
    def post(self):
        args = add_artist_parser.parse_args()
        artist_id = args['artist_id']

        current_user_id = get_jwt_identity()
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
            # Create a new UserPreference instance
            user_pref = UserPreference(user_id=current_user_id)
            db.session.add(user_pref)
            db.session.commit()

            artist = Artist.query.filter_by(spotify_id=artist_id).first()
            if artist:
                user_pref.favorite_artists.append(artist)
                db.session.commit()
                return {'message': 'Artist added to favorites successfully'}, 200
            else:
                return {'message': 'Artist not found'}, 404

    @favourites_ns.doc(security='apikey')
    @jwt_required()
    @favourites_ns.expect(delete_artist_parser, validate=True)
    def delete(self):
        """
        Delete a personal favorite artist for the current user.
        """
        args = delete_artist_parser.parse_args()
        artist_id = args['artist_id']

        current_user_id = get_jwt_identity()

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
            return {'message': 'No favorite artists to remove'}, 404

check_artist_parser = reqparse.RequestParser()
check_artist_parser.add_argument('artist_id', type=str, required=True, help='Artist ID')

@favourites_ns.route('/artists/check')
class CheckFavoriteArtist(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @favourites_ns.expect(check_artist_parser, validate=True)
    def post(self):
        """
        Check if an artist is a personal favorite for the current user.
        """
        args = check_artist_parser.parse_args()
        artist_id = args['artist_id']

        current_user_id = get_jwt_identity()

        user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()
        if user_pref:
            is_favorite = any(artist.spotify_id == artist_id for artist in user_pref.favorite_artists)
            return {'favourite': is_favorite}, 200
        else:
            # Create a new UserPreference instance
            user_pref = UserPreference(user_id=current_user_id)
            db.session.add(user_pref)
            db.session.commit()

            is_favorite = any(artist.spotify_id == artist_id for artist in user_pref.favorite_artists)
            return {'favourite': is_favorite}, 200
        
personal_ns = api.namespace('personal', description='Personal operations')

add_recent_parser = reqparse.RequestParser()  # create an instance of the parser
add_recent_parser.add_argument('spotify_id', required=True, help="Spotify ID is required")
add_recent_parser.add_argument('played_at', type=int, required=True, help="Played at timestamp is required")

@personal_ns.route('/recent/tracks')
class PersonalRecentTracks(Resource):
    @api.doc(security='apikey')
    @jwt_required()
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
    @api.expect(add_recent_parser)
    def post(self):
        args = add_recent_parser.parse_args()  # parse the incoming request

        current_user_id = get_jwt_identity()
        spotify_id = args['spotify_id']
        played_at_timestamp = args['played_at']  # Assuming played_at is a timestamp
        played_at = datetime.fromtimestamp(played_at_timestamp / 1000)

        # Your logic to add a recent track goes here

        return {'message': 'Recent track added successfully'}, 200
    
post_track_parser = reqparse.RequestParser()
post_track_parser.add_argument('spotify_id', type=str, required=True, help='Spotify ID')
delete_parser = reqparse.RequestParser()
delete_parser.add_argument('spotify_id', type=str, required=True, help='Spotify ID of the track to delete')

from sqlalchemy.orm import joinedload

@favourites_ns.route('/tracks')
class PersonalFavoriteTracks(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @api.doc(description="Get a user's favorite tracks",
                responses={
                    200: ("List of favorite tracks", "Track"),
                    404: "No favorite tracks found"
                })
    def get(self):
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
            return {'favourite_tracks': serialized_tracks}, 200
        else:
            return {'message': 'No favorite tracks found'}, 404

    @api.doc(security='apikey')
    @jwt_required()
    @api.expect(post_track_parser, validate=True)
    def post(self):
        try:
            args = post_track_parser.parse_args()
            spotify_id = args['spotify_id']

            current_user_id = get_jwt_identity()
            user_pref = UserPreference.query.filter_by(user_id=current_user_id).first()

            if not user_pref:
                user_pref = UserPreference(user_id=current_user_id)
                db.session.add(user_pref)

            # Check if track already exists
            track = Track.query.filter_by(spotify_id=spotify_id).first()
            if not track:
                access_token = redis.get('spotify_access_token').decode('utf-8')
                sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
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

            return {'message': 'Track added to favorites successfully'}, 200

        except Exception as e:
            return {'error': str(e)}, 500

    @api.doc(security='apikey')
    @jwt_required()
    @api.expect(delete_parser)
    def delete(self):
        args = delete_parser.parse_args()
        current_user_id = get_jwt_identity()
        spotify_id = args['spotify_id']
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

check_parser = reqparse.RequestParser()
check_parser.add_argument('spotify_id', type=str, required=True, help='Spotify ID of the track to check')

@favourites_ns.route('/track/check')
class CheckFavoriteTrack(Resource):
    @api.doc(security='apikey')
    @jwt_required()
    @api.expect(check_parser)
    def post(self):
        """
        Check if a track is a favorite for the current user.
        """
        args = check_parser.parse_args()
        current_user_id = get_jwt_identity()
        spotify_id = args['spotify_id']
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

success_model = api.model('Success', {
    'success': fields.Boolean(description='Indicates whether the operation was successful'),
    'message': fields.String(description='Additional message related to the operation')
})

play_parser = reqparse.RequestParser()
play_parser.add_argument('trackUri', type=str, required=True, help='Spotify URI of the track to play')
play_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to play the track on')

@playback_ns.route('/play')
class PlaybackPlay(Resource):
    @api.doc(description='Start playback of a track on a specified device')
    @api.response(200, 'Success', success_model)
    @api.response(400, 'Bad Request', success_model)
    @api.expect(play_parser)
    def post(self):
        args = play_parser.parse_args()
        access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        track_uri = args['trackUri']
        device_id = args['myDeviceId']

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

pause_parser = reqparse.RequestParser()
pause_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to pause the playback on')

@playback_ns.route('/pause')
class PlaybackPause(Resource):
    @api.doc(description='Pause playback on a specified device')
    @api.response(200, 'Success', success_model)
    @api.response(400, 'Bad Request', success_model)
    @api.expect(pause_parser)
    def post(self):
        args = pause_parser.parse_args()
        access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        device_id = args['myDeviceId']

        sp.pause_playback(device_id=device_id)

        return {'success': True, 'message': 'Playback paused successfully'}, 200

resume_parser = reqparse.RequestParser()
resume_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to resume the playback on')

@playback_ns.route('/resume')
class PlaybackResume(Resource):
    @api.doc(description='Resume playback on a specified device')
    @api.response(200, 'Success', success_model)
    @api.response(400, 'Bad Request', success_model)
    @api.expect(resume_parser)
    def post(self):
        args = resume_parser.parse_args()
        access_token = redis.get('spotify_access_token').decode('utf-8')  # Extract token from request header
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        device_id = args['myDeviceId']

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


next_parser = reqparse.RequestParser()
next_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to play the next track on')

@playback_ns.route('/next')
class NextTrack(Resource):
    @api.expect(next_parser)
    def post(self):
        args = next_parser.parse_args()
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = args['myDeviceId']

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
    
previous_parser = reqparse.RequestParser()
previous_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to play the previous track on')    

@playback_ns.route('/previous')
class PreviousTrack(Resource):
    @api.doc(description='Play the previous track on the specified device')
    @api.expect(previous_parser)
    def post(self):
        args = previous_parser.parse_args()
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = args['myDeviceId']

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

shuffle_parser = reqparse.RequestParser()
shuffle_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to toggle shuffle mode on')
shuffle_parser.add_argument('shuffleState', type=bool, required=True, help='True to enable shuffle, False to disable')

@playback_ns.route('/shuffle')
class Shuffle(Resource):
    @api.doc(description='Toggle shuffle mode on the specified device')
    @api.expect(shuffle_parser)
    def post(self):
        args = shuffle_parser.parse_args()
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = args['myDeviceId']
        shuffle_state = args['shuffleState']

        sp.shuffle(shuffle_state, device_id=device_id)
        return {'success': True, 'message': f'Shuffle {"enabled" if shuffle_state else "disabled"} successfully.'}, 200

repeat_parser = reqparse.RequestParser()
repeat_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to set repeat mode on')
repeat_parser.add_argument('repeatState', type=str, required=True, help='Repeat mode: "track", "context", or "off"')

@playback_ns.route('/repeat')
class Repeat(Resource):
    @api.doc(description='Set repeat mode on the specified device')
    @api.expect(repeat_parser)
    def post(self):
        args = repeat_parser.parse_args()
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = args['myDeviceId']
        repeat_state = args['repeatState']

        sp.repeat(repeat_state, device_id=device_id)
        return {'success': True, 'message': f'Repeat mode set to {repeat_state} successfully.'}, 200

seek_parser = reqparse.RequestParser()
seek_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to seek playback on')
seek_parser.add_argument('newPositionMs', type=int, required=True, help='New position in milliseconds')

@playback_ns.route('/seek')
class Seek(Resource):
    @api.doc(description='Seek playback to a specified position on the currently playing track')
    @api.expect(seek_parser)
    def post(self):
        args = seek_parser.parse_args()
        new_position_ms = args['newPositionMs']
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


current_track_position_parser = reqparse.RequestParser()
current_track_position_parser.add_argument('myDeviceId', type=str, required=True, help='Spotify ID of the device to get the current track position from')

@playback_ns.route('/current_track_position')
class CurrentTrackPosition(Resource):
    @api.doc(description='Get the current position of the playback in milliseconds')
    @api.expect(current_track_position_parser)
    def get(self):
        args = current_track_position_parser.parse_args()
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        device_id = args['myDeviceId']

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

recommend_genres_parser = reqparse.RequestParser()
recommend_genres_parser.add_argument('limit', type=int, required=False, help='Limit the number of genres returned')

@api.route('/recommendation/genres')
class RecommendGenres(Resource):
    @api.doc(description='Get recommended genres')
    @api.expect(recommend_genres_parser)
    def get(self):
        args = recommend_genres_parser.parse_args()
        limit = args.get('limit')

        # Fetch genres from database and format the response
        genres = Genre.query.limit(limit).all() if limit else Genre.query.all()
        genres_list = [{'id': genre.id, 'genre_name': genre.genre_name, 'genre_image': genre.cloudinary_image_url} for genre in genres]
        return {'genres': genres_list}

recommend_tracks_by_genre_parser = reqparse.RequestParser()
recommend_tracks_by_genre_parser.add_argument('genre_name', type=str, required=True, help='The name of the genre')

@api.route('/recommendation/genres/<string:genre_name>')
class RecommendTracksByGenre(Resource):
    @api.doc(params={'genre_name': 'The name of the genre'})
    @api.expect(recommend_tracks_by_genre_parser)
    def get(self, genre_name):
        args = recommend_tracks_by_genre_parser.parse_args()
        genre_name = args['genre_name']
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

recommend_artists_by_genre_parser = reqparse.RequestParser()
recommend_artists_by_genre_parser.add_argument('genre', type=str, required=True, help='The name of the genre')

@api.route('/recommendation/artists/<string:genre>')
class RecommendArtistsByGenre(Resource):
    @api.doc(params={'genre': 'The name of the genre'})
    @api.expect(recommend_artists_by_genre_parser)
    @jwt_required()
    @cache.cached(timeout=3600)  # Cache the result for 1 hour (3600 seconds)
    def get(self, genre):
        args = recommend_artists_by_genre_parser.parse_args()
        genre = args['genre']
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        try:
            sorted_artists = fetch_artists_by_genre(sp, genre)
            return jsonify({'sorted_artists': sorted_artists})
        except spotipy.SpotifyException as e:
            return jsonify({'error': str(e)})

recommend_tracks_by_genre_parser = reqparse.RequestParser()
recommend_tracks_by_genre_parser.add_argument('genre', type=str, required=True, help='The name of the genre')

@api.route('/recommendation/tracks/<string:genre>')
class RecommendTracksByGenre(Resource):
    @api.doc(params={'genre': 'The name of the genre'})
    @api.expect(recommend_tracks_by_genre_parser)
    @jwt_required()
    @cache.cached(timeout=3600)  # Cache the result for 1 hour (3600 seconds)
    def get(self, genre):
        args = recommend_tracks_by_genre_parser.parse_args()
        genre = args['genre']
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)

        try:
            with concurrent.futures.ThreadPoolExecutor() as executor:
                sorted_tracks = executor.submit(fetch_tracks_by_specific_genre, sp, genre).result()
            return jsonify({'sorted_tracks': sorted_tracks})
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

artist_resource_parser = reqparse.RequestParser()
artist_resource_parser.add_argument('artist_id', type=str, required=True, help='The Spotify ID of the artist')

@api.route('/artist/<path:artist_id>')
class ArtistResource(Resource):
    @api.doc(params={'artist_id': 'The Spotify ID of the artist'})
    @api.expect(artist_resource_parser)
    @cache.cached(timeout=3600)
    def get(self, artist_id):
        args = artist_resource_parser.parse_args()
        artist_id = args['artist_id']

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

top_tracks_parser = reqparse.RequestParser()
top_tracks_parser.add_argument('artist_id', type=str, required=True, help='The Spotify ID of the artist')

@api.route('/artist/<path:artist_id>/top-tracks')
class TopTracks(Resource):
    @api.doc(params={'artist_id': 'The Spotify ID of the artist'})
    @api.expect(top_tracks_parser)
    @cache.cached(timeout=3600)  # Cache the result for 1 hour (3600 seconds)
    def get(self, artist_id):
        args = top_tracks_parser.parse_args()
        artist_id = args['artist_id']
        access_token = redis.get('spotify_access_token').decode('utf-8')
        sp = spotipy.Spotify(auth_manager=sp_oauth, auth=access_token)
        return fetch_artist_top_tracks(sp, [artist_id])
            
login_parser = reqparse.RequestParser()
login_parser.add_argument('username', type=str, required=True, help='Username is required')
login_parser.add_argument('password', type=str, required=True, help='Password is required')
        
@api.route('/login')
class Login(Resource):
    @api.expect(login_parser)
    def post(self):
        args = login_parser.parse_args()
        
        username = args.get('username')
        password = args.get('password')

        if not username or not password:
            return {'error': 'Username and password required'}, 400

        user = User.query.filter_by(username=username).first()

        if not user or not check_password_hash(user.password_hash, password):
            return {'error': 'Invalid username or password'}, 401

        existing_refresh_token = RefreshToken.query.filter_by(user_id=user.id).first()

        if existing_refresh_token:
            refresh_token = existing_refresh_token.jti
        else:
            refresh_token = create_refresh_token(identity=user.id)
            insert_refresh_token(refresh_token, user.id)

        # Create access token
        access_token = create_access_token(identity=user.id, expires_delta=timedelta(days=3))

        # Create response
        resp = make_response({
            'username': user.username,
            'email' : user.email,
            'role' : user.role
        })

        # Set the cookies
        set_access_cookies(resp, access_token)
        set_refresh_cookies(resp, refresh_token)

        return resp

check_auth_parser = reqparse.RequestParser()
check_auth_parser.add_argument('token', type=str, required=True, help='Token is required')

@api.route('/check-auth')
class CheckAuth(Resource):
    @api.expect(check_auth_parser)
    def get(self):
        args = check_auth_parser.parse_args()
        token = args['token']
        try:
            verify_jwt_in_request()
            return {'isAuthenticated': True}, 200
        except:
            return {'isAuthenticated': False}, 401
        
        
register_parser = reqparse.RequestParser()
register_parser.add_argument('username', type=str, required=True, help='Username is required')
register_parser.add_argument('email', type=str, required=True, help='Email is required')
register_parser.add_argument('password', type=str, required=True, help='Password is required')

@api.route('/register')
class Register(Resource):
    @api.expect(register_parser)
    def post(self):
        # Parse the incoming request
        args = register_parser.parse_args()

        # Extract the username, email, and password from the parsed request
        username = args.get('username')
        email = args.get('email')
        password = args.get('password')

        # Check if the user already exists
        existing_user = User.query.filter_by(username=username).first()

        if existing_user:
            return {'message': 'Username already exists'}, 400

        # Create a new user
        new_user = User(username=username, email=email, password=password)
        db.session.add(new_user)
        db.session.commit()
        return {'message': 'Registration successful'}, 201
    
refresh_parser = reqparse.RequestParser()
refresh_parser.add_argument('refresh_token', type=str, required=True, help='Refresh token is required')

@app.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    args = refresh_parser.parse_args()
    refresh_token = args['refresh_token']

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
    
    return token_info['access_token']
        
def check_token():
    if int(time.time()) > int(redis.get('expires_at') or 0) - 300:
        refresh_spotify_token()
        print("Token will expire in 5 minutes, force refresh now")
    

# Route for refreshing Spotify token
spotify_ns = api.namespace('spotify', description='Spotify related operations')

spotify_refresh_parser = reqparse.RequestParser()
spotify_refresh_parser.add_argument('refresh_token', type=str, required=True, help='Refresh token is required')

@spotify_ns.route('/refresh')
class SpotifyRefresh(Resource):
    @spotify_ns.expect(spotify_refresh_parser)
    def post(self):
        args = spotify_refresh_parser.parse_args()
        refresh_token = args['refresh_token']

        access_token, expires_at = refresh_spotify_token()

        if expires_at is None:
            # Handle the case where 'expires_at' is not in token_info
            # For example, you might return an error message
            return {'error': 'expires_at not found in token_info'}, 400

        return {'message': 'Access token refreshed successfully', 'spotify_token' : access_token, 'spotify_expires_at' : expires_at}, 200
    
profile_put_parser = reqparse.RequestParser()
profile_put_parser.add_argument('username', type=str, required=False, help='Username')
profile_put_parser.add_argument('email', type=str, required=False, help='Email')    
    
@api.route('/profile')
class UserProfile(Resource):
    @api.doc(security='Bearer')
    @jwt_required()
    def get(self):
        current_user_id = get_jwt_identity()
        user = db.session.get(User, current_user_id)
        if not user:
            return {'message': 'User not found'}, 404
        profile_data = {
            'id': current_user_id,
            'username': user.username,
            'role' : user.role,
        }
        return {"profile" : profile_data}, 200
    
    @api.doc(security='Bearer')
    @jwt_required()
    def put(self):
        args = profile_put_parser.parse_args()
        username = args['username']
        email = args['email']

        current_user_id = get_jwt_identity()
        current_user = User.query.get(current_user_id)
        if not current_user:
            return {'message': 'User not found'}, 404

        if username:
            user_with_same_username = User.query.filter_by(username=username).first()
            if user_with_same_username and user_with_same_username.id != current_user_id:
                return {'exists_name': True}, 200

        if email:
            user_with_same_email = User.query.filter_by(email=email).first()
            if user_with_same_email and user_with_same_email.id != current_user_id:
                return {'exists_email': True}, 200

        if username:
            current_user.username = username
        if email:
            current_user.email = email

        db.session.commit()

        return {'message': 'Profile updated successfully'}, 200

@api.route('/logout')
class UserLogout(Resource):
    @api.doc(security='Bearer Auth')
    @jwt_required()
    def post(self):
        # Create the response object
        response = make_response({'message': 'User logged out'})
        unset_jwt_cookies(response)
        return {'message': 'User logged out'}, 200


# @api.route('/email')
# class EmailAPI(Resource):
#     def post(self):
#         """
#         Send Email.
        
#         This endpoint sends an email using SMTP with the provided parameters.
#         """
#         data = request.json
#         sender_email = data.get('sender_email')
#         sender_password = data.get('sender_password')
#         recipient_email = data.get('recipient_email')
#         subject = data.get('subject')
#         template_name = data.get('template_name')
#         template_vars = data.get('template_vars')

#         try:
#             send_email(sender_email, sender_password, recipient_email, subject, template_name, **template_vars)
#             return {'message': 'Email sent successfully'}, 200
#         except Exception as e:
#             return {'error': str(e)}, 500
        
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


if __name__ == "__main__":
    app.run(debug=True, port=5003)
