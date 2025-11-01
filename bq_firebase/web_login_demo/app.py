"""Flask application for Firebase Web Login Demo."""
from collections.abc import Callable
from functools import wraps
import logging
import os
from typing import Any

from config import Config
from flask import Flask
from flask import jsonify
from flask import redirect
from flask import render_template
from flask import request
from flask import session
from flask import url_for
from google.auth.exceptions import GoogleAuthError
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from werkzeug.wrappers import Response

app = Flask(__name__)
app.config.from_object(Config)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# OAuth flow configuration - controlled by environment variable
if os.getenv('OAUTHLIB_INSECURE_TRANSPORT', '0') == '1':
    logger.warning(
        'OAUTHLIB_INSECURE_TRANSPORT enabled - '
        'ONLY use in development, NEVER in production'
    )
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'


def _create_oauth_flow(state: str | None = None) -> Flow:
    """Create OAuth flow configuration.

    Args:
        state: Optional state parameter for OAuth flow.

    Returns:
        Configured Flow instance.
    """
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
    return flow


def login_required(f: Callable) -> Callable:
    """Decorator to require login for routes.

    Args:
        f: The function to wrap with login requirement.

    Returns:
        Decorated function that redirects to index if not authenticated.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if 'credentials' not in session:
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated_function


@app.route('/')
def index() -> str:
    """Render login page.

    Returns:
        Rendered HTML template for the login page.
    """
    return render_template('index.html')


@app.route('/api/config')
def get_config() -> Response:
    """Return Firebase configuration for client-side SDK.

    Returns:
        JSON response containing Firebase, GA4, and OAuth configuration.
    """
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
def auth_google() -> Response:
    """Initiate Google OAuth flow.

    Returns:
        Redirect response to Google OAuth authorization URL.
    """
    flow = _create_oauth_flow()
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        include_granted_scopes='true',
        prompt='consent'
    )

    session['state'] = state
    return redirect(authorization_url)


@app.route('/auth/callback')
def auth_callback() -> Response:
    """Handle OAuth callback.

    Returns:
        Redirect response to success page.

    Raises:
        GoogleAuthError: If OAuth authentication fails.
    """
    state = session.get('state')
    flow = _create_oauth_flow(state=state)

    try:
        flow.fetch_token(authorization_response=request.url)
    except GoogleAuthError:
        logger.error("OAuth authentication failed", exc_info=True)
        return redirect(url_for('index'))

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
def success() -> str:
    """Render success page with user data.

    Returns:
        Rendered HTML template for the success page.
    """
    return render_template('success.html')


@app.route('/api/user-info')
@login_required
def get_user_info() -> Response | tuple[Response, int]:
    """Get user information from Google APIs.

    Returns:
        JSON response containing user profile and YouTube channel data,
        or error response with status code.
    """
    creds_dict = session['credentials']
    credentials = Credentials(
        token=creds_dict['token'],
        refresh_token=creds_dict.get('refresh_token'),
        token_uri=creds_dict.get('token_uri'),
        client_id=creds_dict.get('client_id'),
        client_secret=creds_dict.get('client_secret'),
        scopes=creds_dict.get('scopes')
    )

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
                    'thumbnail': (
                        channel['snippet']['thumbnails']['default']['url']
                    ),
                    'subscriberCount': (
                        channel['statistics'].get('subscriberCount', '0')
                    ),
                    'videoCount': (
                        channel['statistics'].get('videoCount', '0')
                    ),
                    'viewCount': (
                        channel['statistics'].get('viewCount', '0')
                    ),
                    'publishedAt': channel['snippet']['publishedAt']
                }
        except HttpError:
            logger.error("YouTube API error", exc_info=True)
            youtube_data = {
                'error': 'No YouTube channel found or access denied'
            }

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

    except GoogleAuthError:
        logger.error("Google API authentication error", exc_info=True)
        return jsonify({'error': 'Authentication failed'}), 401
    except HttpError:
        logger.error("Google API HTTP error", exc_info=True)
        return jsonify({'error': 'API request failed'}), 500
    except Exception:
        logger.error("Unexpected error in get_user_info", exc_info=True)
        return jsonify({'error': 'Internal server error'}), 500


@app.route('/logout')
def logout() -> Response:
    """Clear session and logout.

    Returns:
        Redirect response to index page.
    """
    session.clear()
    return redirect(url_for('index'))


if __name__ == '__main__':
    try:
        Config.validate()
        app.run(debug=Config.DEBUG, port=5000)
    except ValueError as e:
        logger.error("Configuration error: %s", str(e))
        logger.error(
            "Please check your .env file and ensure all required "
            "variables are set."
        )
