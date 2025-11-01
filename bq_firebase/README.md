# Firebase Web Login Demo

A complete demonstration of Google Single Sign-On (SSO) with Firebase Authentication, YouTube Data API integration, and Google Analytics 4 event tracking with BigQuery export.

## Features

- Google OAuth 2.0 authentication via Firebase
- YouTube channel data collection (read-only access)
- Google Analytics 4 event tracking
- Automatic BigQuery export of analytics events
- Clean, responsive UI
- Real-time data display

## Architecture

```
User → Login Page → Google OAuth → Success Page
                         ↓
                   YouTube API
                         ↓
                   GA4 Events → BigQuery
```

## Prerequisites

1. **Python 3.12+** with `uv` package manager
2. **Firebase Project** with Authentication enabled
3. **Google Cloud Project** with:
   - OAuth 2.0 credentials configured
   - YouTube Data API v3 enabled
   - Google Analytics 4 property created
   - BigQuery export enabled for GA4

## Setup Instructions

### 1. Install Dependencies

```bash
# Navigate to project directory
cd bq_firebase

# Install dependencies using uv
uv sync

# Activate virtual environment
source .venv/bin/activate  # On macOS/Linux
# or
.venv\Scripts\activate  # On Windows
```

### 2. Firebase Configuration

1. Go to [Firebase Console](https://console.firebase.google.com/)
2. Select your project
3. Navigate to Project Settings → General
4. Copy your Firebase configuration values
5. Enable Google Sign-In:
   - Go to Authentication → Sign-in method
   - Enable Google provider

### 3. Google Cloud Console Setup

#### OAuth 2.0 Credentials

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to APIs & Services → Credentials
3. Create OAuth 2.0 Client ID:
   - Application type: Web application
   - Authorized redirect URIs: `http://localhost:5000/auth/callback`
4. Copy Client ID and Client Secret

#### Enable YouTube Data API

1. Navigate to APIs & Services → Library
2. Search for "YouTube Data API v3"
3. Click Enable

### 4. Google Analytics 4 Setup

1. Go to [Google Analytics](https://analytics.google.com/)
2. Create or select a GA4 property
3. Get your Measurement ID (format: G-XXXXXXXXXX)
4. Enable BigQuery export:
   - Navigate to Admin → BigQuery Links
   - Link your BigQuery project
   - Configure daily export

### 5. Environment Configuration

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` with your actual values:
   ```bash
   # Firebase Configuration
   FIREBASE_API_KEY=AIzaSy...
   FIREBASE_AUTH_DOMAIN=your-project.firebaseapp.com
   FIREBASE_PROJECT_ID=your-project-id
   FIREBASE_STORAGE_BUCKET=your-project.appspot.com
   FIREBASE_MESSAGING_SENDER_ID=123456789
   FIREBASE_APP_ID=1:123456789:web:abc123

   # Google Analytics 4
   GA4_MEASUREMENT_ID=G-XXXXXXXXXX

   # Google OAuth 2.0
   GOOGLE_CLIENT_ID=123456789-abc.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=GOCSPX-abc123

   # Flask
   SECRET_KEY=generate-a-random-secret-key
   DEBUG=True
   ```

3. Generate a secure secret key:
   ```bash
   python -c "import secrets; print(secrets.token_hex(32))"
   ```

## Running the Application

```bash
# Make sure you're in the project directory
cd bq_firebase

# Activate virtual environment
source .venv/bin/activate

# Run the Flask application
cd web_login_demo
python app.py
```

The application will start at `http://localhost:5000`

## Usage

1. **Login Page** (`http://localhost:5000`)
   - Click "Sign in with Google"
   - Authorize the application
   - Grant YouTube read-only access (optional)

2. **Success Page** (`http://localhost:5000/success`)
   - View your Google account information
   - See YouTube channel statistics (if available)
   - Review tracked analytics events

3. **Logout**
   - Click the "Logout" button to clear session

## Analytics Events Tracked

The application tracks the following GA4 events:

| Event Name | Description | Parameters |
|------------|-------------|------------|
| `page_view` | Page viewed | `page_title`, `page_location` |
| `login_initiated` | User clicked login button | `method: google` |
| `login_success` | Successful authentication | `method: google` |
| `user_profile_loaded` | User profile retrieved | `user_id`, `email_verified` |
| `youtube_data_collected` | YouTube data retrieved | `channel_id`, `subscriber_count`, `video_count`, `view_count` |
| `error` | Error occurred | `error_message`, `error_location` |

## BigQuery Integration

### Viewing Events in BigQuery

Once GA4 export is configured, events will appear in BigQuery:

```sql
-- View recent events
SELECT
  event_date,
  event_name,
  user_pseudo_id,
  event_params
FROM `your-project.analytics_XXXXXXXXX.events_*`
WHERE _TABLE_SUFFIX = FORMAT_DATE('%Y%m%d', CURRENT_DATE())
ORDER BY event_timestamp DESC
LIMIT 100;
```

### Analyzing YouTube Data

```sql
-- Extract YouTube metrics from events
SELECT
  user_pseudo_id,
  event_timestamp,
  (SELECT value.string_value FROM UNNEST(event_params) WHERE key = 'channel_id') as channel_id,
  (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'subscriber_count') as subscribers,
  (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'video_count') as videos,
  (SELECT value.int_value FROM UNNEST(event_params) WHERE key = 'view_count') as views
FROM `your-project.analytics_XXXXXXXXX.events_*`
WHERE event_name = 'youtube_data_collected'
  AND _TABLE_SUFFIX = FORMAT_DATE('%Y%m%d', CURRENT_DATE());
```

## Project Structure

```
bq_firebase/
├── web_login_demo/
│   ├── app.py                 # Flask application
│   ├── config.py              # Configuration management
│   ├── static/
│   │   ├── css/
│   │   │   └── style.css      # Styling
│   │   └── js/
│   │       └── app.js         # Frontend logic & GA4 tracking
│   └── templates/
│       ├── index.html         # Login page
│       └── success.html       # Success page
├── .env                       # Environment variables (not in git)
├── .env.example               # Environment template
├── pyproject.toml             # Python dependencies
└── README_DEMO.md            # This file
```

## Security Considerations

1. **Never commit `.env` file** - Contains sensitive credentials
2. **Use HTTPS in production** - Currently using HTTP for development
3. **Rotate secrets regularly** - Change SECRET_KEY and API keys periodically
4. **Limit OAuth scopes** - Only request necessary permissions
5. **Validate redirect URIs** - Ensure OAuth callbacks are secure

## Troubleshooting

### Import Errors

If you see import errors for Flask or Google libraries:
```bash
uv sync
source .venv/bin/activate
```

### OAuth Redirect URI Mismatch

Ensure your OAuth redirect URI in Google Cloud Console matches:
```
http://localhost:5000/auth/callback
```

### YouTube Data Not Showing

- Verify the user has a YouTube channel
- Check that YouTube Data API v3 is enabled
- Ensure OAuth consent includes YouTube scope

### GA4 Events Not Appearing

- Check that GA4_MEASUREMENT_ID is correct
- Verify events in GA4 DebugView (real-time)
- BigQuery export has 24-48 hour delay

### Configuration Errors

If you see "Missing required configuration" error:
- Verify all required variables in `.env`
- Check for typos in variable names
- Ensure no extra spaces in values

## Development

### Adding New Events

To track additional events, use the `trackEvent` function in `app.js`:

```javascript
trackEvent('custom_event_name', {
    param1: 'value1',
    param2: 'value2'
});
```

### Modifying OAuth Scopes

Edit `OAUTH_SCOPES` in `config.py`:

```python
OAUTH_SCOPES = [
    'openid',
    'https://www.googleapis.com/auth/userinfo.email',
    'https://www.googleapis.com/auth/userinfo.profile',
    'https://www.googleapis.com/auth/youtube.readonly',
    # Add more scopes as needed
]
```

## Resources

- [Firebase Documentation](https://firebase.google.com/docs)
- [Google Analytics 4 Documentation](https://developers.google.com/analytics/devguides/collection/ga4)
- [YouTube Data API](https://developers.google.com/youtube/v3)
- [BigQuery Documentation](https://cloud.google.com/bigquery/docs)
- [Flask Documentation](https://flask.palletsprojects.com/)

## License

This is a demonstration project for educational purposes.
