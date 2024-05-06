from flask import Flask, render_template, redirect, url_for, request, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
    set_access_cookies, set_refresh_cookies, unset_jwt_cookies, verify_jwt_in_request,
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_caching import Cache
from flask_cors import CORS
from flask_restx import Api, Resource, fields, reqparse

from functools import wraps

import requests
import sys
import random
import pandas as pd
# from flask_oauthlib.client import OAuth
from models.Admin import Admin
from models.User import User
from models.Payment import Payment
from models.Room import Room
from models.RefreshToken import RefreshToken
from models.UserPreference import UserPreference
from models.Track import Track
from models.Artist import Artist
from database import db
from datetime import datetime, timedelta
from werkzeug.middleware.profiler import ProfilerMiddleware
from sqlalchemy.exc import IntegrityError
from sqlalchemy import func

from datetime import timedelta

import spotipy
from spotipy import Spotify
from spotipy.oauth2 import SpotifyOAuth

app = Flask(__name__)
CORS(app, origins=["http://localhost:3001"], supports_credentials=True)

# config section

client_id = 'f8eb39f738654c94945537405e6ebad1'
client_secret = '27e1646b17d24a32b34cfaf6504a84b1'
redirect_uri = 'http://127.0.0.1:5000/admin/callback'

sp_oauth = SpotifyOAuth(
    client_id=client_id,
    client_secret=client_secret,
    redirect_uri=redirect_uri,
    scope='user-library-read'  # Add the required scopes for your application   
)

cache = Cache(app, config={'CACHE_TYPE': 'simple', 'CACHE_DEFAULT_TIMEOUT': 60})

jwt = JWTManager(app)
jwt.init_app(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'mysql+mysqlconnector://root:Delta1006@127.0.0.1/pyppo' #=> Change to MySQL database
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SECRET_KEY'] = 'Moriarty'
app.config['JWT_SECRET_KEY'] = 'your-secret-key'  # Change this!
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(days=3)


app.config["CACHE_DEFAULT_TIMEOUT"] = 60  # Set the cache timeout in seconds

app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_SECURE'] = True
app.config['JWT_COOKIE_SAMESITE'] = 'None'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['JWT_COOKIE_CSRF_PROTECT'] = False

db.init_app(app)

with app.app_context():
    db.create_all()
    # Commit the changes to the database
    db.session.commit()
    print("TABLES CREATED")
    
    if not Admin.query.first():
        # If no records, create an initial admin
        initial_admin = Admin(name='Super Admin', email='sAdmin@admin.com', username='sAdmin', password='sPassword', datetime=datetime.now(), priority=True)
        db.session.add(initial_admin)
        db.session.commit()
        
authorizations = {
    'Bearer Auth': {
        'type': 'apiKey',
        'in': 'header',
        'name': 'Authorization'
    }
}   
        
api = Api(app, doc='/api', version='1.0', title='Pyppo Web Music Admin API', description='', authorizations=authorizations)
        
@app.route('/')
def index():
    return jsonify({'status': 'success', 'message': 'Welcome to the Admin API!'})
        
track = api.model('Track', {
    'id': fields.Integer(required=True, description='The track identifier'),
    'name': fields.String(required=True, description='The track name'),
    # Add other track fields here
})

@api.route('/tracks')
class TrackList(Resource):
    @api.doc('list_tracks')
    @api.marshal_list_with(track)
    @jwt_required()
    def get(self):
        tracks = Track.query.all()
        return tracks, 200
    
artist = api.model('Artist', {
    'id': fields.Integer(required=True, description='The artist identifier'),
    'name': fields.String(required=True, description='The artist name'),
    # Add other artist fields here
})

@api.route('/artists')
class ArtistList(Resource):
    @api.doc('list_artists')
    @api.marshal_list_with(artist)
    @jwt_required()
    def get(self):
        artists = Artist.query.all()
        return artists, 200
    
user = api.model('User', {
    'id': fields.Integer(required=True, description='The user identifier'),
    'username': fields.String(required=True, description='The username'),
    'email': fields.String(required=True, description='The email'),
    'role': fields.String(required=True, description='The role'),
    # Add other user fields here
})
    
@api.route('/users')
class UserList(Resource):
    @api.doc('list_users')
    @api.marshal_list_with(user)
    @jwt_required()
    def get(self):
        users = User.query.all()
        return users, 200
    
@jwt_required()
def get_all_users():
    # Query the database for all users
    users = User.query.all()

    # Convert the users to a list of dictionaries
    users_dict = [{'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role} for user in users]

    # Return the users as JSON
    return jsonify(users_dict), 200

@api.route('/users/regular/count')
class RegularUsersCount(Resource):
    @api.doc('get_regular_users_count')
    def get(self):
        count = User.query.filter_by(role='regular').count()
        return {'regular_users_count': count}, 200

@api.route('/users/premium/count')
class PremiumUsersCount(Resource):
    @api.doc('get_premium_users_count')
    def get(self):
        count = User.query.filter_by(role='premium').count()
        return {'premium_users_count': count}, 200
    
@api.route('/payment/total')
class TotalPayment(Resource):
    @api.doc('get_total_payment')
    def get(self):
        total = db.session.query(db.func.sum(Payment.amount)).scalar()
        return {'total_payment': total}, 200

@api.route('/payment/increase')
class PaymentIncrease(Resource):
    @api.doc('get_payment_increase')
    def get(self):
        today = datetime.today().date()
        yesterday = today - timedelta(days=1)

        today_total = db.session.query(func.sum(Payment.amount)).filter(func.date(Payment.created_at) == today).scalar() or 0
        yesterday_total = db.session.query(func.sum(Payment.amount)).filter(func.date(Payment.created_at) == yesterday).scalar() or 0

        if yesterday_total > 0:
            increase = ((today_total - yesterday_total) / yesterday_total) * 100
        else:
            increase = 0

        return {'payment_increase': increase}, 200
    
@api.route('/payment/total/last-two-weeks')
class TotalPaymentsLastTwoWeeks(Resource):
    @api.doc('get_total_payments_last_two_weeks')
    def get(self):
        today = datetime.today().date()
        two_weeks_ago = today - timedelta(days=14)

        payments = db.session.query(func.date(Payment.created_at), func.sum(Payment.amount)).filter(func.date(Payment.created_at) >= two_weeks_ago).group_by(func.date(Payment.created_at)).all()

        if not payments:
            return [], 200

        payments_grouped_by_date = {}
        for payment in payments:
            date = payment[0].isoformat()
            if date not in payments_grouped_by_date:
                payments_grouped_by_date[date] = payment[1]
            else:
                payments_grouped_by_date[date] += payment[1]

        payments_dict = [{'date': date, 'total_payment': total_payment} for date, total_payment in payments_grouped_by_date.items()]

        return payments_dict, 200
    
@api.route('/most-loved-tracks')
class MostLovedTracks(Resource):
    @api.doc('most_loved_tracks')
    @jwt_required()
    def get(self):
        try:
            most_loved_tracks = db.session.query(Track, db.func.count(UserPreference.id)). \
                join(UserPreference.favorite_tracks). \
                group_by(Track). \
                order_by(db.func.count(UserPreference.id).desc()). \
                limit(10).all()

            result = [{'track_name': track.name, 'total_loves': total_loves} for track, total_loves in most_loved_tracks]

            return {'most_loved_tracks': result}, 200
        except Exception as e:
            return {'error': str(e)}, 500
        
profile_parser = reqparse.RequestParser()
profile_parser.add_argument('name', type=str, location='json', required=False)
profile_parser.add_argument('email', type=str, location='json', required=False)
profile_parser.add_argument('company', type=str, location='json', required=False)
profile_parser.add_argument('job', type=str, location='json', required=False)
profile_parser.add_argument('country', type=str, location='json', required=False)
profile_parser.add_argument('address', type=str, location='json', required=False)
profile_parser.add_argument('phone', type=str, location='json', required=False)

@api.route('/profile')
class Profile(Resource):
    @api.doc('profile')
    @jwt_required()
    def get(self):
        current_admin = get_jwt_identity()
        admin = Admin.query.filter_by(username=current_admin).first()

        if admin is None:
            return {"msg": "Admin not found"}, 404

        admin_dict = admin.to_dict()
        for key, value in admin_dict.items():
            if isinstance(value, datetime):
                admin_dict[key] = value.isoformat()

        return admin_dict, 200
    
    @api.doc('profile')
    @api.expect(profile_parser)
    @jwt_required()
    def put(self):
        current_admin = get_jwt_identity()
        admin = Admin.query.filter_by(username=current_admin).first()

        if admin is None:
            return {"msg": "Admin not found"}, 404

        args = profile_parser.parse_args()

        if args['name']:
            admin.name = args['name']
        if args['email']:
            admin.email = args['email']
        if args['company']:
            admin.company = args['company']
        if args['job']:
            admin.job = args['job']
        if args['country']:
            admin.country = args['country']
        if args['address']:
            admin.address = args['address']
        if args['phone']:
            admin.phone = args['phone']

        db.session.commit()
        
        admin_dict = admin.to_dict()
        
        for key, value in admin_dict.items():
            if isinstance(value, datetime):
                admin_dict[key] = value.isoformat()

        return admin_dict, 200
        
parser = reqparse.RequestParser()
parser.add_argument('username', type=str, required=True, help="Username is required")
parser.add_argument('password', type=str, required=True, help="Password is required")


@api.route('/login')
class Login(Resource):
    @api.doc('login')
    @api.expect(parser)
    def post(self):
        args = parser.parse_args()

        username = args['username']
        password = args['password']

        admin = Admin.query.filter_by(username=username).first()
        if admin is None or not admin.check_password(password):
            return {"msg": "Bad username or password"}, 401

        access_token = create_access_token(identity=username)

        # Check if the admin has a refresh token in the database
        refresh_token_record = RefreshToken.query.filter_by(admin_id=admin.id).first()
        if not refresh_token_record:
            # If not, create a new one
            refresh_token = create_refresh_token(identity=username)
            issued_at = datetime(2024, 4, 20, 19, 48, 13, 724876)

            # 'expires_in' is 30 days from 'issued_at'
            expires_in = issued_at + timedelta(days=30)
            new_refresh_token = RefreshToken(admin_id=admin.id, jti=refresh_token, expires_in=expires_in)
            db.session.add(new_refresh_token)
            db.session.commit()
        else:
            # If yes, use the existing one
            refresh_token = refresh_token_record.jti

        resp = jsonify({'login': True})
        set_access_cookies(resp, access_token)
        set_refresh_cookies(resp, refresh_token)
        return resp
        
@api.route('/logout')
class Logout(Resource):
    def post(self):
        resp = make_response({'logout': True}, 200)
        unset_jwt_cookies(resp)
        return resp
    
@api.route('/room-creation-activities')
class RoomCreationActivities(Resource):
    def get(self):
        try:
            room_creation_activities = db.session.query(Room.name, User.username, Room.creation_time). \
                join(User, Room.host_id == User.id). \
                order_by(Room.creation_time.desc()).all()

            if room_creation_activities:
                activities = []
                for room_name, creator_username, creation_time in room_creation_activities:
                    activity = {
                        'room_name': room_name,
                        'creator_username': creator_username,
                        'creation_time': creation_time.strftime('%Y-%m-%d %H:%M:%S')
                    }
                    activities.append(activity)
                return {'activities': activities}, 200
            else:
                return {'message': 'No room creation activities found'}, 404
        except Exception as e:
            return {'error': str(e)}, 500

@api.route('/check-admin-authentication')
class CheckAdminAuthentication(Resource):
    @jwt_required()
    def get(self):
        username = get_jwt_identity()
        admin = Admin.query.filter_by(username=username).first()
        if admin:
            return {'isAdminAuthenticated': True}, 200
        else:
            return {'isAdminAuthenticated': False}, 403
        
if __name__ == "__main__":
    app.run(debug=True, port=5004)