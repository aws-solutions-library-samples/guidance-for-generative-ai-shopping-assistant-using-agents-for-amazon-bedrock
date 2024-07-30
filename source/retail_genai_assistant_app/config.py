# config.py
from dotenv import load_dotenv
import os
import boto3
from streamlit_cognito_auth import CognitoAuthenticator, CognitoHostedUIAuthenticator
from streamlit_cognito_auth.session_provider import Boto3SessionProvider


# Load environment variables from .env file
load_dotenv()

# Retrieve Cognito configuration from environment variables
USER_POOL_ID = os.getenv("USER_POOL_ID")
CLIENT_ID = os.getenv("USER_POOL_CLIENT_ID")
CLIENT_SECRET = os.getenv("USER_POOL_CLIENT_SECRET")
COGNITO_DOMAIN = os.getenv("USER_POOL_DOMAIN")
APP_URL = os.getenv("APP_URL")
region = os.environ["AWS_REGION"]
aws_account_id = os.environ["AWS_ACCOUNT_ID"]


session_provider = Boto3SessionProvider(
    region=region,
    account_id=aws_account_id,
    user_pool_id=USER_POOL_ID,
    identity_pool_id=CLIENT_ID,
)

# # Configure the authenticator
# authenticator = CognitoAuthenticator(
#     pool_id= USER_POOL_ID,
#     app_client_id= CLIENT_ID,
#     app_client_secret= CLIENT_SECRET
# )

authenticator = CognitoHostedUIAuthenticator(
    pool_id= USER_POOL_ID,
    app_client_id= CLIENT_ID,
    app_client_secret= CLIENT_SECRET,
    use_cookies=False,
    cognito_domain = COGNITO_DOMAIN,
    redirect_uri = APP_URL

)
def get_authenticator():
    return authenticator


