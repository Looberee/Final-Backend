from database import db

class RefreshToken(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    token = db.Column(db.Text, nullable=False)
    # spotify_token = db.Column(db.Text, nullable=False)
    user_id = db.Column(db.Integer, nullable=False)

    def __init__(self, token=None, user_id=None, spotify_token=None):
        self.token = token
        self.user_id = user_id
        # self.spotify_token = spotify_token

# Function to generate and store refresh token in the database
def insert_refresh_token(refresh_token, user_id):
    token_record = RefreshToken(token=refresh_token, user_id=user_id)
    db.session.add(token_record)
    db.session.commit()
    return refresh_token

# Function to check if refresh token exists in the database
def is_valid_refresh_token(refresh_token):
    return RefreshToken.query.filter_by(token=refresh_token).first() is not None

# Function to delete refresh token from the database
# def delete_refresh_token(refresh_token):
#     token_record = RefreshToken.query.filter_by(token=refresh_token).first()
#     if token_record:
#         db.session.delete(token_record)
#         db.session.commit()
        
        
# # Function to generate and store refresh token in the database
# def insert_spotify_refresh_token(refresh_token, user_id):
#     token_record = RefreshToken(spotify_token=refresh_token, user_id=user_id)
#     db.session.add(token_record)
#     db.session.commit()
#     return refresh_token

# # Function to check if refresh token exists in the database
# def is_valid_spotify_refresh_token(refresh_token):
#     return RefreshToken.query.filter_by(spotify_token=refresh_token).first() is not None

# # Function to delete refresh token from the database
# def delete_spotify_refresh_token(refresh_token):
#     token_record = RefreshToken.query.filter_by(spotify_token=refresh_token).first()
#     if token_record:
#         db.session.delete(token_record)
#         db.session.commit()
