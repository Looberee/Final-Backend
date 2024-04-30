import pytest
import json
from user_server import app  # replace with the actual import of your Flask app
from unittest import mock
from unittest.mock import MagicMock, patch
from database import db
from flask import Flask
from models.Genre import Genre  # Assuming you have a Genre model defined
from flask_jwt_extended import create_access_token  # Add import statement

@pytest.fixture
def app_context():
    app = Flask(__name__)
    # Configure your app here

    with app.app_context():
        yield app


@pytest.fixture
def auth(client):
    class AuthActions:
        def login(self):
            # Replace with your actual login logic
            return 'fake-jwt-token'

        def create_playlist(self, name):
            # Replace with your actual playlist creation logic
            pass

    return AuthActions()

@pytest.fixture
def client():
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client

def test_get_pyppo_dashboard(client):
    response = client.get('/home')
    assert response.status_code == 200
    
def test_search_route(client, mocker):
    # Mock the return value of redis.get('spotify_access_token')
    mocker.patch('user_server.redis.get').return_value.decode.return_value = 'fake_access_token'

    # Mock the return value of Spotify search method
    mocker.patch('user_server.spotipy.Spotify.search').return_value = {
        'tracks': {
            'items': [
                {
                    'id': 'fake_track_id',
                    'name': 'Fake Track',
                    'artists': [{'name': 'Fake Artist'}],
                    'duration_ms': 300000,
                    'album': {'images': [{'url': 'fake_image_url'}]}
                }
            ]
        },
        'artists': {
            'items': [
                {
                    'id': 'fake_artist_id',
                    'name': 'Fake Artist',
                    'images': [{'url': 'fake_artist_image_url'}]
                }
            ]
        }
    }

    # Make a GET request to the '/search' route with a fake query
    response = client.get('/search?query=fake_query')

    # Assert the response status code
    assert response.status_code == 200

    # Parse the JSON response
    data = json.loads(response.data)

    # Assert the structure of the response
    assert 'search_results' in data
    assert 'artists_results' in data

    # Assert the content of the response
    assert len(data['search_results']) == 1
    assert len(data['artists_results']) == 1


    print("Search results:", data['search_results'])
    # Assert the content of the search results
    assert data['search_results'][0]['id'] == 1
    assert data['search_results'][0]['name'] == 'Fake Track'
    assert data['search_results'][0]['artists'] == 'Fake Artist'
    assert data['search_results'][0]['duration'] == 300000
    assert data['search_results'][0]['spotify_image_url'] == 'fake_image_url'

    # Assert the content of the artists results
    assert data['search_results'][0]['id'] == 1
    assert data['artists_results'][0]['name'] == 'Fake Artist'
    assert data['artists_results'][0]['spotify_image_url'] == 'fake_artist_image_url'

from werkzeug.security import generate_password_hash, check_password_hash

class MockUser:
    def __init__(self, id, username, email, role, password_hash):
        self.id = id
        self.username = username
        self.email = email
        self.role = role
        self.password_hash = password_hash
        
class MockUserPlaylist:
    def __init__(self, id, name, user_id):
        self.id = id
        self.name = name
        self.user_id = user_id

def mock_check_password_hash(pw_hash, password):
    return check_password_hash(pw_hash, password)

def test_login(client, monkeypatch):
    # Use the app context
    with app.app_context():
        # Define mock data
        mock_username = 'testuser'
        mock_password = 'testpassword'
        hashed_password = generate_password_hash(mock_password)
        mock_user = MockUser(1, mock_username, 'testuser@example.com', 'regular', hashed_password)
        mock_access_token = 'mock_access_token'
        mock_refresh_token = 'mock_refresh_token'
        mock_spotify_token = 'mock_spotify_token'

        # Mock User.query.filter_by
        mock_query = MagicMock()
        mock_query.filter_by().first.return_value = mock_user
        monkeypatch.setattr('user_server.User.query', mock_query)


        # Mock check_password_hash
        monkeypatch.setattr('user_server.check_password_hash', mock_check_password_hash)

        # Mock create_refresh_token
        monkeypatch.setattr('user_server.create_refresh_token', lambda identity: mock_refresh_token)

        # Mock insert_refresh_token
        mock_insert_refresh_token = MagicMock()
        monkeypatch.setattr('user_server.insert_refresh_token', mock_insert_refresh_token)

        # Mock create_access_token
        monkeypatch.setattr('user_server.create_access_token', lambda identity, expires_delta: mock_access_token)

        # Mock redis.get
        monkeypatch.setattr('user_server.redis.get', lambda x: mock_spotify_token.encode('utf-8'))


        # Create a test client for the Flask app
        client = app.test_client()

        # Send request to the route
        response = client.post('/login', json={'username': mock_username, 'password': mock_password})

        # Check status code
        assert response.status_code == 200

        # Check JSON response
        data = response.get_json()
        assert 'profile' in data
        assert 'login' in data
        assert 'access_token' in data
        assert 'refresh_token' in data
        assert 'spotify_token' in data

        # Check profile data
        profile = data['profile']
        assert profile['username'] == mock_username
        assert profile['email'] == 'testuser@example.com'
        assert profile['role'] == 'regular'

        # Check login flag
        assert data['login'] == True

        # Check access token
        assert data['access_token'] == mock_access_token

        # Check refresh token
        assert data['refresh_token'] == mock_refresh_token

        # Check Spotify token
        assert data['spotify_token'] == mock_spotify_token
    
class MockGenre:
    def __init__(self, id, genre_name, cloudinary_image_url):
        self.id = id
        self.genre_name = genre_name
        self.cloudinary_image_url = cloudinary_image_url

def test_recommend_genres(client):
    # Define mock data for Genre query
    mock_genres = [
        Genre(genre_name='acoustic', cloudinary_image_url='https://res.cloudinary.com/dckgpl1ys/image/upload/v1711094909/acoustic.jpg'),
        Genre(genre_name='afrobeat', cloudinary_image_url='https://res.cloudinary.com/dckgpl1ys/image/upload/v1711094910/afrobeat.jpg')
    ]

    # Mock the query attribute of db.session
    mock_query = MagicMock()
    mock_query.all = MagicMock(return_value=mock_genres)
    with patch('database.db.session.query', mock_query):
        # Send a request to the endpoint
        response = client.get('/recommendation/genres')

        # Check status code
        assert response.status_code == 200

        # Check JSON response
        data = response.get_json()
        assert 'genres' in data
        assert len(data['genres']) == 21

        # Check the content of each genre in the response
        for genre_info, mock_genre in zip(data['genres'], mock_genres):
            assert genre_info['genre_name'] == mock_genre.genre_name
            assert genre_info['genre_image'] == mock_genre.cloudinary_image_url
            
            
from contextlib import contextmanager
            
@contextmanager
def mock_request_context(data):
    with app.test_request_context(method='POST', json=data):
        yield
            
def test_register(client):
    # Define mock data for registration
    mock_data = {
        'username': 'testuser1',
        'email': 'testuser1@example.com',
        'password': 'testpassword'
    }

    # Mock the request.json attribute
    response = client.post('/register', json=mock_data)
    
    print(response.get_json())

        # Check status code
    assert response.status_code == 201

    # Check JSON response
    data = response.get_json()
    assert 'message' in data
    assert data['message'] == 'Registration successful'
