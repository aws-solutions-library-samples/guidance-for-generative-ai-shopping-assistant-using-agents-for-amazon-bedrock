# config.py
from dotenv import load_dotenv
import os
from streamlit_cognito_auth import CognitoAuthenticator

# Load environment variables from .env file
load_dotenv()

# Retrieve Cognito configuration from environment variables
USER_POOL_ID = os.getenv("USER_POOL_ID")
CLIENT_ID = os.getenv("USER_POOL_CLIENT_ID")
CLIENT_SECRET = os.getenv("USER_POOL_CLIENT_SECRET")
COGNITO_DOMAIN = os.getenv("USER_POOL_DOMAIN")
APP_URL = os.getenv("APP_URL")

# Configure the authenticator
authenticator = CognitoAuthenticator(
    pool_id= USER_POOL_ID,
    app_client_id= CLIENT_ID,
    app_client_secret= CLIENT_SECRET
)

def get_authenticator():
    return authenticator
