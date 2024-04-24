from flask import Flask
from flask_jwt_extended import jwt_required, get_jwt_identity
from flask_restx import Api, Resource, fields
from models import UserPlaylist, UserPlaylistTrack

app = Flask(__name__)
api = Api(app, doc='/api')

playlist_ns = api.namespace('personal', description='Personal playlists operations')

playlist_model = api.model('Playlist', {
    'id': fields.Integer,
    'name': fields.String,
    'tracks_count': fields.Integer,
    'encode_id': fields.String
})

@playlist_ns.route('/playlists')  # Remove the /api prefix here
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

if __name__ == "__main__":
    app.run(debug=True, port=5003)
