# auth.py
import os
import base64
from utils.config import Config
from dotenv import load_dotenv
from datetime import datetime, timezone
import requests
import urllib.parse
import streamlit as st
import jwt

def initialize_session_vars():
    """Initialize Streamlit session state variables."""
    if 'config' not in st.session_state:
        st.session_state.config = Config()
    if 'user_authenticated' not in st.session_state:
        st.session_state.user_authenticated = False
    if 'user_profile' not in st.session_state:
        st.session_state.user_profile = None
    if 'access_token' not in st.session_state:
        st.session_state.access_token = None
    if 'auth_result' not in st.session_state:
        st.session_state.auth_result = None
    if 'auth_code' not in st.session_state:
        st.session_state.auth_code = None

def reset_session_state():
    """Reset session state variables related to authentication."""
    st.session_state.user_authenticated = False
    st.session_state.user_profile = None
    st.session_state.access_token = None
    st.session_state.auth_code = None


def decode_jwt(token):
    """Decode JWT token."""
    try:
        payload = jwt.decode(token, algorithms=['ES256'], options={"verify_signature": False})
        # st.write('USER', payload)
        #print(payload)
        return payload
    except jwt.DecodeError:
        print('error')
        return None

def is_token_expired(token):
    """Check if the token is expired."""
    decoded_token = decode_jwt(token)
    exp_timestamp = decoded_token['exp']
    current_timestamp = datetime.now(timezone.utc).timestamp()
    return current_timestamp > exp_timestamp

def get_info_from_amz_header(amz_header):
    try:
        payload = jwt.decode(amz_header, algorithms=['ES256'], options={"verify_signature": False})
        # st.write('USER', payload)
        #print(payload)
        return payload
    except jwt.DecodeError:
        print('error')
        return None


def get_tokens(auth_code):
    """Exchange auth code for tokens."""
    token_url = f"{st.session_state.config.COGNITO_DOMAIN}/oauth2/token"
    auth = base64.b64encode(f"{st.session_state.config.COGNITO_CLIENT_ID}:{st.session_state.config.COGNITO_CLIENT_SECRET}".encode()).decode()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth}'
    }
    data = {
        'grant_type': 'authorization_code',
        "client_id": st.session_state.config.COGNITO_CLIENT_ID,
        'code': auth_code,
        'redirect_uri': st.session_state.config.REDIRECT_URI,
    }
    response = requests.post(token_url, headers=headers, data=data)
    if response.status_code == 200:
            return response.json()
    return None

def refresh_token(refresh_token):
    """Refresh access token using refresh token."""
    token_url = f"{st.session_state.config.COGNITO_DOMAIN}/oauth2/token"
    auth = base64.b64encode(f"{st.session_state.config.COGNITO_CLIENT_ID}:{st.session_state.config.COGNITO_CLIENT_SECRET}".encode()).decode()
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Authorization': f'Basic {auth}'
    }
    data = {
        'grant_type': 'refresh_token',
        'refresh_token': refresh_token,
        'client_id': st.session_state.config.COGNITO_CLIENT_ID,
    }
    response = requests.post(token_url, headers=headers, data=data)
    return response.json()

def get_cognito_login_url():
    """Generate Cognito login URL."""
    query_params = {
        "client_id": st.session_state.config.COGNITO_CLIENT_ID,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": st.session_state.config.REDIRECT_URI
    }
    url = f"{st.session_state.config.COGNITO_DOMAIN}/login?{urllib.parse.urlencode(query_params)}"
    #st.write('get_cognito_login_url', url)
    return url

def get_logout_state():
    # Generate a unique state value
    session_unique_id = f"Logout_State_{st.session_state.config.COGNITO_CLIENT_ID}"
    state = base64.urlsafe_b64encode(session_unique_id.encode()).decode()
    return state

def get_cognito_logout_url():
    """Generate Cognito logout URL."""

    url = (
        f"{st.session_state.config.COGNITO_DOMAIN}/logout?"
        f"response_type=code&"
        f"client_id={st.session_state.config.COGNITO_CLIENT_ID}&"
        f"redirect_uri={st.session_state.config.REDIRECT_URI}&"
        f"state={get_logout_state()}&"
        f"scope=openid profile email"
    )

    # url = f"{COGNITO_DOMAIN}/logout?client_id={COGNITO_CLIENT_ID}&logout_uri={REDIRECT_URI}"

    st.write('get_cognito_logout_url', url)
    return url

def authenticate_user():
    
    """Authenticate user based on ALB headers or OAuth2 flow."""
    initialize_session_vars()

    # Validate logout state after redirecting from Cognito Login page using logout redirect_uri
    query_params = st.query_params.to_dict()
    if 'state' in query_params:
        logout_state = query_params.get('state')
        validate_state = get_logout_state()
        query_params.pop('state')
        st.query_params.from_dict(query_params)
        if logout_state != validate_state:
            return False
    
    # Handle OAuth2 Redirect and Token Management if ALB headers are not present
    query_params =  st.query_params
    if 'code' in query_params:
        # st.write('In code')
        auth_code = query_params.get('code')
        if st.session_state.auth_code != auth_code:
            st.session_state.auth_result = get_tokens(auth_code)
            st.session_state.auth_code = auth_code

    if st.session_state.auth_result is not None:
        # st.write('In auth_result')
        id_token = st.session_state.auth_result['id_token']
        access_token = st.session_state.auth_result['access_token']
        refresh_token_value = st.session_state.auth_result['refresh_token']

        # Check if tokens are expired and refresh if necessary
        if is_token_expired(id_token) or is_token_expired(access_token):
            new_tokens = refresh_token(refresh_token_value)
            if 'id_token' in new_tokens and 'access_token' in new_tokens:
                st.session_state.auth_result.update(new_tokens)
                id_token = new_tokens['id_token']
                access_token = new_tokens['access_token']
                st.session_state.access_token = access_token
                st.session_state.user_profile = decode_jwt(id_token)
                st.session_state.user_authenticated = True
            else:
                reset_session_state()
                return False
        else:
            st.session_state.user_profile = decode_jwt(id_token)
            st.session_state.access_token = access_token
            st.session_state.user_authenticated = True
            return True

    # Check for ALB authentication headers
    headers = st.context.headers
    
    if 'X-Amzn-Oidc-Data' in headers and 'X-Amzn-Oidc-Accesstoken' in headers:
        # if st.session_state.auth_status != 'logged_out':
            
        # else:
        #     return False
        st.write('In headers')

        oidc_data = headers['X-Amzn-Oidc-Data']
        access_token = headers['X-Amzn-Oidc-Accesstoken']
        st.write('headers', oidc_data, access_token)
        
        try:
            if not st.session_state.user_authenticated or st.session_state.access_token != access_token:
                st.write('token set userfingo')
                user_info = get_info_from_amz_header(oidc_data)
                st.write('user info', user_info)
                st.session_state.user_profile = user_info
                st.session_state.access_token = access_token
                st.session_state.user_authenticated = True
                st.session_state.auth_status = 'logged_in'
            elif is_token_expired(access_token):
                st.write('token expired')
                reset_session_state()
            return st.session_state.user_authenticated

        except Exception as e:
            reset_session_state()
            return False
 
    
    return False


def logout():
    """Logout user and clear cookies."""
    reset_session_state()
    st.query_params.clear()
    logout_url = get_cognito_logout_url()

    # Invalidate AWSELBSessionCookie to perform successful logout on Cognito Hosted UI. Does not work with Streamlit today
    # expire =datetime.now() - timedelta(hours=1)
    # cookie_manager.set('AWSELBAuthSessionCookie-0', '', key='set_AWSELBAuthSessionCookie-0', expires_at=expire, path='/')
    # cookie_manager.set('AWSELBAuthSessionCookie-1', '', key='set_AWSELBAuthSessionCookie-1', expires_at=expire, path='/')
    
    st.markdown(f'<meta http-equiv="refresh" content="0;url={logout_url}">', unsafe_allow_html=True)
    st.stop()
