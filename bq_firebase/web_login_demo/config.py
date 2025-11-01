"""Configuration for Firebase Web Login Demo."""
import os
from typing import ClassVar

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration.

    Loads configuration from environment variables and provides
    validation for required settings.
    """

    # Flask
    SECRET_KEY: ClassVar[str] = os.getenv(
        'SECRET_KEY', 'dev-secret-key-change-in-production'
    )
    DEBUG: ClassVar[bool] = os.getenv('DEBUG', 'True').lower() == 'true'

    # Firebase
    FIREBASE_API_KEY: ClassVar[str | None] = os.getenv('FIREBASE_API_KEY')
    FIREBASE_AUTH_DOMAIN: ClassVar[str | None] = os.getenv(
        'FIREBASE_AUTH_DOMAIN'
    )
    FIREBASE_PROJECT_ID: ClassVar[str | None] = os.getenv(
        'FIREBASE_PROJECT_ID'
    )
    FIREBASE_STORAGE_BUCKET: ClassVar[str | None] = os.getenv(
        'FIREBASE_STORAGE_BUCKET'
    )
    FIREBASE_MESSAGING_SENDER_ID: ClassVar[str | None] = os.getenv(
        'FIREBASE_MESSAGING_SENDER_ID'
    )
    FIREBASE_APP_ID: ClassVar[str | None] = os.getenv('FIREBASE_APP_ID')

    # Google Analytics 4
    GA4_MEASUREMENT_ID: ClassVar[str | None] = os.getenv(
        'GA4_MEASUREMENT_ID'
    )

    # Google OAuth
    GOOGLE_CLIENT_ID: ClassVar[str | None] = os.getenv('GOOGLE_CLIENT_ID')
    GOOGLE_CLIENT_SECRET: ClassVar[str | None] = os.getenv(
        'GOOGLE_CLIENT_SECRET'
    )

    # OAuth Scopes
    OAUTH_SCOPES: ClassVar[list[str]] = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile',
        'https://www.googleapis.com/auth/youtube.readonly'
    ]

    @classmethod
    def validate(cls) -> None:
        """Validate required configuration.

        Raises:
            ValueError: If any required configuration variables are missing.
        """
        required = [
            'FIREBASE_API_KEY',
            'FIREBASE_AUTH_DOMAIN',
            'FIREBASE_PROJECT_ID',
            'GA4_MEASUREMENT_ID',
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET'
        ]
        missing = [key for key in required if not getattr(cls, key)]
        if missing:
            raise ValueError(
                f"Missing required configuration: {', '.join(missing)}"
            )
