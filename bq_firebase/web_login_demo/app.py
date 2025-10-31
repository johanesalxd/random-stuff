"""Flask application for Firebase Web Login Demo."""
from functools import wraps
import json
import os

from config import Config
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

app = Flask(__name__)
app.config.from_object(Config)

# OAuth flow configuration
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'  # For development only


def login_required(f):
    """Decorator to require login for routes."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'credentials' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index():
    """Render login page."""
    return render_template('index.html')


@app.route('/api/config')
def get_config():
    """Return Firebase configuration for client-side SDK."""
    return jsonify({
        'firebase': {
            'apiKey': Config.FIREBASE_API_KEY,
            'authDomain': Config.FIREBASE_AUTH_DOMAIN,
            'projectId': Config.FIREBASE_PROJECT_ID,
            'storageBucket': Config.FIREBASE_STORAGE_BUCKET,
            'messagingSenderId': Config.FIREBASE_MESSAGING_SENDER_ID,
            'appId': Config.FIREBASE_APP_ID
        },
        'ga4': {
            'measurementId': Config.GA4_MEASUREMENT_ID
        },
        'oauth': {
            'clientId': Config.GOOGLE_CLIENT_ID,
            'scopes': Config.OAUTH_SCOPES
        }
    })


@app.route('/auth/google')
def auth_google():
    """Initiate Google OAuth flow."""
    flow = Flow.from_client_config(
        {
            'web': {
                'client_id': Config.GOOGLE_CLIENT_ID,
                'client_secret': Config.GOOGLE_CLIENT_SECRET,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [request.url_root + 'auth/callback']
            }
        },
        scopes=Config.OAUTH_SCOPES
    )

    flow.redirect_uri = request.url_root + 'auth/callback'
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    session['state'] = state
    return redirect(authorization_url)


@app.route('/auth/callback')
def auth_callback():
    """Handle OAuth callback."""
    state = session.get('state')

    flow = Flow.from_client_config(
        {
            'web': {
                'client_id': Config.GOOGLE_CLIENT_ID,
                'client_secret': Config.GOOGLE_CLIENT_SECRET,
                'auth_uri': 'https://accounts.google.com/o/oauth2/auth',
                'token_uri': 'https://oauth2.googleapis.com/token',
                'redirect_uris': [request.url_root + 'auth/callback']
            }
        },
        scopes=Config.OAUTH_SCOPES,
        state=state
    )

    flow.redirect_uri = request.url_root + 'auth/callback'
    flow.fetch_token(authorization_response=request.url)

    credentials = flow.credentials
    session['credentials'] = {
        'token': credentials.token,
        'refresh_token': credentials.refresh_token,
        'token_uri': credentials.token_uri,
        'client_id': credentials.client_id,
        'client_secret': credentials.client_secret,
        'scopes': credentials.scopes
    }

    return redirect(url_for('success'))


@app.route('/success')
@login_required
def success():
    """Render success page with user data."""
    return render_template('success.html')


@app.route('/api/user-info')
@login_required
def get_user_info():
    """Get user information from Google APIs."""
    credentials = Credentials(**session['credentials'])

    try:
        # Get user profile
        oauth2_service = build('oauth2', 'v2', credentials=credentials)
        user_info = oauth2_service.userinfo().get().execute()

        # Get YouTube channel info
        youtube_data = None
        try:
            youtube = build('youtube', 'v3', credentials=credentials)
            channels_response = youtube.channels().list(
                part='snippet,statistics,contentDetails',
                mine=True
            ).execute()

            if channels_response.get('items'):
                channel = channels_response['items'][0]
                youtube_data = {
                    'channelId': channel['id'],
                    'channelTitle': channel['snippet']['title'],
                    'description': channel['snippet']['description'],
                    'thumbnail': channel['snippet']['thumbnails']['default']['url'],
                    'subscriberCount': channel['statistics'].get('subscriberCount', '0'),
                    'videoCount': channel['statistics'].get('videoCount', '0'),
                    'viewCount': channel['statistics'].get('viewCount', '0'),
                    'publishedAt': channel['snippet']['publishedAt']
                }
        except Exception as e:
            print(f"YouTube API error: {e}")
            youtube_data = {
                'error': 'No YouTube channel found or access denied'}

        return jsonify({
            'user': {
                'id': user_info.get('id'),
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'picture': user_info.get('picture'),
                'verified_email': user_info.get('verified_email')
            },
            'youtube': youtube_data
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/logout')
def logout():
    """Clear session and logout."""
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    try:
        Config.validate()
        app.run(debug=Config.DEBUG, port=5000)
    except ValueError as e:
        print(f"Configuration error: {e}")
        print("Please check your .env file and ensure all required variables are set.")
