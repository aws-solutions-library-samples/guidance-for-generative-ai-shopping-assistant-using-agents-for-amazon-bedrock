import os
import streamlit as st
from dotenv import load_dotenv
import requests
import base64
import json
import jwt

# ------------------------------------
# Read constants from environment file
# ------------------------------------
load_dotenv()
COGNITO_DOMAIN = os.environ.get("USER_POOL_DOMAIN")
CLIENT_ID = os.environ.get("USER_POOL_CLIENT_ID")
CLIENT_SECRET = os.environ.get("USER_POOL_CLIENT_SECRET")
APP_URI = os.environ.get("APP_URL")


# ------------------------------------
# Initialise Streamlit state variables
# ------------------------------------
def initialise_st_state_vars():
    """
    Initialise Streamlit state variables.

    Returns:
        Nothing.
    """
    if "auth_code" not in st.session_state:
        st.session_state["auth_code"] = ""
    if "authenticated" not in st.session_state:
        st.session_state["authenticated"] = False
    if "user_cognito_groups" not in st.session_state:
        st.session_state["user_cognito_groups"] = []
    if "user_info" not in st.session_state:
        st.session_state["user_info"] = None
        


# ----------------------------------
# Get authorization code after login
# ----------------------------------
def get_auth_code():
    """
    Gets auth_code state variable.

    Returns:
        Nothing.
    """
    
    try:
       auth_code = st.query_params.get('code')
    except (KeyError, TypeError):
        auth_code = ""

    return auth_code


# ----------------------------------
# Set authorization code after login
# ----------------------------------
def set_auth_code():
    """
    Sets auth_code state variable.

    Returns:
        Nothing.
    """
    initialise_st_state_vars()
    auth_code = get_auth_code()
    st.session_state["auth_code"] = auth_code


# -------------------------------------------------------
# Use authorization code to get user access and id tokens
# -------------------------------------------------------
def get_user_tokens(auth_code):
    """
    Gets user tokens by making a post request call.

    Args:
        auth_code: Authorization code from cognito server.

    Returns:
        {
        'access_token': access token from cognito server if user is successfully authenticated.
        'id_token': access token from cognito server if user is successfully authenticated.
        }

    """

    # Variables to make a post request
    token_url = f"{COGNITO_DOMAIN}/oauth2/token"
    client_secret_string = f"{CLIENT_ID}:{CLIENT_SECRET}"
    client_secret_encoded = str(
        base64.b64encode(client_secret_string.encode("utf-8")), "utf-8"
    )
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "Authorization": f"Basic {client_secret_encoded}",
    }
    body = {
        "grant_type": "authorization_code",
        "client_id": CLIENT_ID,
        "code": auth_code,
        "redirect_uri": APP_URI,
    }

    token_response = requests.post(token_url, headers=headers, data=body)
    try:
        access_token = token_response.json()["access_token"]
        id_token = token_response.json()["id_token"]
    except (KeyError, TypeError):
        access_token = ""
        id_token = ""

    return access_token, id_token


# ---------------------------------------------
# Use access token to retrieve user information
# ---------------------------------------------
def get_user_info(access_token):
    """
    Gets user info from aws cognito server.

    Args:
        access_token: string access token from the aws cognito user pool
        retrieved using the access code.

    Returns:
        userinfo_response: json object.
    """
    userinfo_url = f"{COGNITO_DOMAIN}/oauth2/userInfo"
    headers = {
        "Content-Type": "application/json;charset=UTF-8",
        "Authorization": f"Bearer {access_token}",
    }

    userinfo_response = requests.get(userinfo_url, headers=headers)

    return userinfo_response.json()

def get_user_info_from_token(id_token):
    try:
        payload = jwt.decode(id_token, options={"verify_signature": False})
        #print(payload)
        return {
            'username': payload.get('cognito:username'),
            'email': payload.get('email'),
            'name': payload.get('name')
        }
    except jwt.DecodeError:
        return None
        
# -------------------------------------------------------
# Decode access token to JWT to get user's cognito groups
# -------------------------------------------------------
# Ref - https://gist.github.com/GuillaumeDerval/b300af6d4f906f38a051351afab3b95c
def pad_base64(data):
    """
    Makes sure base64 data is padded.

    Args:
        data: base64 token string.

    Returns:
        data: padded token string.
    """
    missing_padding = len(data) % 4
    if missing_padding != 0:
        data += "=" * (4 - missing_padding)
    return data


def get_user_cognito_groups(id_token):
    """
    Decode id token to get user cognito groups.

    Args:
        id_token: id token of a successfully authenticated user.

    Returns:
        user_cognito_groups: a list of all the cognito groups the user belongs to.
    """
    user_cognito_groups = []
    if id_token != "":
        header, payload, signature = id_token.split(".")
        printable_payload = base64.urlsafe_b64decode(pad_base64(payload))
        payload_dict = json.loads(printable_payload)
        try:
            user_cognito_groups = list(dict(payload_dict)["cognito:groups"])
        except (KeyError, TypeError):
            pass
    return user_cognito_groups

def get_user_info_from_amz_header(amz_header):
    try:
        decoded_info = json.loads(base64.b64decode(amz_header).decode('utf-8'))
        return {
            'username': decoded_info.get('username'),
            'email': decoded_info.get('email')
        }
    except:
        return None

# -----------------------------
# Set Streamlit state variables
# -----------------------------
def set_st_state_vars():
    """
    Sets the streamlit state variables after user authentication.
    Returns:
        Nothing.
    """
    print('running')
    initialise_st_state_vars()

    # Check for ALB auth cookie
    alb_auth_cookie = st.context.cookies.get('AWSELBAuthSessionCookie-0')
    
    if alb_auth_cookie:
        # If ALB auth cookie exists, use AMZ header for user details
        amz_header = st.context.headers.get('x-amzn-oidc-data')
        if amz_header:
            user_info = get_user_info_from_amz_header(amz_header)
            if user_info:
                st.session_state.user_info = user_info
                st.session_state["authenticated"] = True
                # You might need to adjust how you get cognito groups from the AMZ header
                st.session_state["user_cognito_groups"] = []  # Update this as needed
                return
            
    auth_code = get_auth_code()
    access_token, id_token = get_user_tokens(auth_code)
    user_cognito_groups = get_user_cognito_groups(id_token)
    user_info = get_user_info_from_token(id_token)

    if access_token != "":
        st.session_state["auth_code"] = auth_code
        st.session_state.user_info = user_info
        st.session_state["authenticated"] = True
        st.session_state["user_cognito_groups"] = user_cognito_groups


# -----------------------------
# Login/ Logout HTML components
# -----------------------------
login_link = f"{COGNITO_DOMAIN}/login?client_id={CLIENT_ID}&response_type=code&scope=email+openid&redirect_uri={APP_URI}"
logout_link = f"{COGNITO_DOMAIN}/logout?client_id={CLIENT_ID}&logout_uri={APP_URI}"

html_css_login = """
<style>
.button-login {
  background-color: skyblue;
  color: white !important;
  padding: 1em 1.5em;
  text-decoration: none;
  text-transform: uppercase;
}

.button-login:hover {
  background-color: #555;
  text-decoration: none;
}

.button-login:active {
  background-color: black;
}

</style>
"""

html_button_login = (
    html_css_login
    + f"<a href='{login_link}' class='button-login' target='_self'>Log In</a>"
)
html_button_logout = (
    html_css_login
    + f"<a href='{logout_link}' class='button-login' target='_self'>Log Out</a>"
)


def button_login():
    """

    Returns:
        Html of the login button.
    """
    return st.sidebar.markdown(f"{html_button_login}", unsafe_allow_html=True)


def button_logout():
    """

    Returns:
        Html of the logout button.
    """
    return st.sidebar.markdown(f"{html_button_logout}", unsafe_allow_html=True)