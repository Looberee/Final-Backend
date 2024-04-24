from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token, create_refresh_token,
    jwt_required, get_jwt_identity,
    set_access_cookies, set_refresh_cookies, unset_jwt_cookies, verify_jwt_in_request
)
from werkzeug.security import check_password_hash, generate_password_hash
from flask_caching import Cache
from flask_cors import CORS

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
        
        
# app.wsgi_app = ProfilerMiddleware(app.wsgi_app, profile_dir='./server_status')


@app.route('/')
def index():
    return jsonify({'status':'OK'}, 200)

@app.route('/tracks')
@jwt_required()
def get_all_tracks():
    # Query the database for all tracks
    tracks = Track.query.all()

    # Convert the tracks to a list of dictionaries
    tracks_dict = [track.to_dict() for track in tracks]

    # Return the tracks as JSON
    return jsonify(tracks_dict), 200

@app.route('/users')
@jwt_required()
def get_all_users():
    # Query the database for all users
    users = User.query.all()

    # Convert the users to a list of dictionaries
    users_dict = [{'id': user.id, 'username': user.username, 'email': user.email, 'role': user.role} for user in users]

    # Return the users as JSON
    return jsonify(users_dict), 200

@app.route('/users/regular/count')
def get_regular_users_count():
    # Query the database for the count of regular users
    count = User.query.filter_by(role='regular').count()

    # Return the count as JSON
    return jsonify({'regular_users_count': count}), 200

@app.route('/users/premium/count')
def get_premium_users_count():
    # Query the database for the count of premium users
    count = User.query.filter_by(role='premium').count()

    # Return the count as JSON
    return jsonify({'premium_users_count': count}), 200

@app.route('/payment/total')
def get_total_payment():
    # Query the database for the sum of all payments
    total = db.session.query(db.func.sum(Payment.amount)).scalar()

    # Return the total as JSON
    return jsonify({'total_payment': total}), 200


@app.route('/payment/increase')
def get_payment_increase():
    # Get today and yesterday's dates
    today = datetime.today().date()
    yesterday = today - timedelta(days=1)

    # Query the database for the sum of today's and yesterday's payments
    today_total = db.session.query(func.sum(Payment.amount)).filter(func.date(Payment.created_at) == today).scalar() or 0
    yesterday_total = db.session.query(func.sum(Payment.amount)).filter(func.date(Payment.created_at) == yesterday).scalar() or 0

    # Calculate the percentage increase
    if yesterday_total > 0:
        increase = ((today_total - yesterday_total) / yesterday_total) * 100
    else:
        increase = 0

    # Return the increase as JSON
    return jsonify({'payment_increase': increase}), 200

@app.route('/payment/total/last-two-weeks')
def get_total_payments_last_two_weeks():
    # Get the current date and the date two weeks ago
    today = datetime.today().date()
    two_weeks_ago = today - timedelta(days=14)

    # Query the database for the sum of payments for each day over the past two weeks
    payments = db.session.query(func.date(Payment.created_at), func.sum(Payment.amount)).filter(func.date(Payment.created_at) >= two_weeks_ago).group_by(func.date(Payment.created_at)).all()

    # If there are no payments, return an empty list
    if not payments:
        return jsonify([]), 200

    # Group the payments by date and sum the amounts for each date
    payments_grouped_by_date = {}
    for payment in payments:
        date = payment[0].isoformat()
        if date not in payments_grouped_by_date:
            payments_grouped_by_date[date] = payment[1]
        else:
            payments_grouped_by_date[date] += payment[1]

    # Convert the result to a list of dictionaries for all days
    payments_dict = [{'date': date, 'total_payment': total_payment} for date, total_payment in payments_grouped_by_date.items()]

    # Return the list as JSON
    return jsonify(payments_dict), 200

@app.route('/most-loved-tracks', methods=['GET'])
@jwt_required()
def most_loved_tracks():
    try:
        # Query the database to get the most loved tracks
        most_loved_tracks = db.session.query(Track, db.func.count(UserPreference.id)). \
            join(UserPreference.favorite_tracks). \
            group_by(Track). \
            order_by(db.func.count(UserPreference.id).desc()). \
            limit(10).all()

        # Format the result
        result = [{'track_name': track.name, 'total_loves': total_loves} for track, total_loves in most_loved_tracks]

        return jsonify({'most_loved_tracks': result}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admins')
@jwt_required()
def get_all_admins():
    # Query the database for all admins
    admins = Admin.query.all()

    # Convert the admins to a list of dictionaries
    admins_dict = [{'id': admin.id, 'name' : admin.name ,'username': admin.username, 'email': admin.email, 'date' : admin.date ,'priority': admin.priority} for admin in admins]

    # Return the admins as JSON
    return jsonify(admins_dict), 200


@app.route('/profile')
@jwt_required()
def profile():
    current_admin = get_jwt_identity()
    admin = Admin.query.filter_by(username=current_admin).first()
    
    if admin is None:
        return jsonify({"msg": "Admin not found"}), 404
    
    return jsonify(admin.to_dict()), 200

@app.route('/profile', methods=['PUT'])
@jwt_required()
def edit_profile():
    current_admin = get_jwt_identity()
    admin = Admin.query.filter_by(username=current_admin).first()
    
    if admin is None:
        return jsonify({"msg": "Admin not found"}), 404
    
    data = request.json
    
    if 'name' in data:
        admin.name = data['name']
    if 'email' in data:
        admin.email = data['email']
    if 'company' in data:
        admin.company = data['company']
    if 'job' in data:
        admin.job = data['job']
    if 'country' in data:
        admin.country = data['country']
    if 'address' in data:
        admin.address = data['address']
    if 'phone' in data:
        admin.phone = data['phone']
    
    db.session.commit()
    
    return jsonify(admin.to_dict()), 200

@app.route('/login', methods=['POST'])
def login():
    username = request.json.get('username', None)
    password = request.json.get('password', None)
    
    if not username:
        return jsonify({"msg": "Missing username parameter"}), 400
    if not password:
        return jsonify({"msg": "Missing password parameter"}), 400

    admin = Admin.query.filter_by(username=username).first()
    if admin is None or not admin.check_password(password):
        return jsonify({"msg": "Bad username or password"}), 401

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
    return resp, 200


@app.route('/register', methods=['POST'])
def register_admin():
    # Get form data
    name = request.json.get('name')
    email = request.json.get('email')
    username = request.json.get('username')
    password = request.json.get('password')

    # Check if any field is missing
    if not (name and email and username and password):
        return jsonify({"msg": "Missing required fields"}), 400

    # Check if admin already exists
    existing_admin = Admin.query.filter_by(username=username).first()
    if existing_admin:
        return jsonify({"msg": "Admin already exists"}), 400

    # Create a new admin
    new_admin = Admin(name=name, email=email, username=username, password=password, datetime=datetime.now(), priority=False)

    # Add the new admin to the database
    db.session.add(new_admin)
    db.session.commit()

    return jsonify({"msg": "Admin created successfully"}), 201

@app.route('/logout', methods=['POST'])
def logout():
    # Create a response
    resp = jsonify({'logout': True})

    # Unset the JWT cookies
    unset_jwt_cookies(resp)

    # Return the response
    return resp, 200

@app.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user = get_jwt_identity()
    access_token = create_access_token(identity=current_user)
    resp = jsonify({'refresh': True})
    set_access_cookies(resp, access_token)
    return resp, 200

@app.route('/room-creation-activities', methods=['GET'])
def room_creation_activities():
    try:
        # Query the database to get room creation activities
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
            return jsonify({'activities': activities}), 200
        else:
            return jsonify({'message': 'No room creation activities found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
@app.route('/check-admin-authentication')
@jwt_required()
def check_admin_authentication():
    username = get_jwt_identity()
    admin = Admin.query.filter_by(username=username).first()
    if admin:
        return jsonify({'isAdminAuthenticated': True}), 200
    else:
        return jsonify({'isAdminAuthenticated': False}), 403

if __name__ == '__main__':
    app.run(debug=True, port=5009)
