import os
import requests
import jwt
import base64
import json
from urllib.parse import urlencode
from dotenv import load_dotenv
import streamlit as st
import time
from extra_streamlit_components import CookieManager
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

class CognitoAuthenticator:
    def __init__(self):
        self.COGNITO_DOMAIN = os.environ.get('USER_POOL_DOMAIN')
        self.CLIENT_ID = os.environ.get('USER_POOL_CLIENT_ID')
        self.CLIENT_SECRET = os.environ.get('USER_POOL_CLIENT_SECRET')
        self.APP_URI = os.environ.get('APP_URL')
        self.TOKEN_ENDPOINT = f"{self.COGNITO_DOMAIN}/oauth2/token"
        self.JWKS_URL = f"{self.COGNITO_DOMAIN}/.well-known/jwks.json"
        self.cookie_manager = CookieManager(key="unique_cookie_key")

    def get_login_url(self):
        query_params = {
            "client_id": self.CLIENT_ID,
            "response_type": "code",
            "scope": "openid email profile",
            "redirect_uri": f"{self.APP_URI}"
        }
        return f"{self.COGNITO_DOMAIN}/login?{urlencode(query_params)}"

    def get_logout_url(self):
        return f"{self.COGNITO_DOMAIN}/logout?client_id={self.CLIENT_ID}&logout_uri={self.APP_URI}"

    def get_auth_code(self):
        return st.query_params.get("code")

    def load_credentials(self):
        cookies = self.cookie_manager.get_all('load_all_credentials')
        time.sleep(0.3)
        return cookies

    def set_credentials(self, token_response):
        print('set_credentials')
        expiration_time = datetime.now() + timedelta(seconds=token_response.get("expires_in"))
        self.cookie_manager.set("id_token", token_response.get("id_token"), expires_at=expiration_time, key="set_id_token")
        self.cookie_manager.set("access_token", token_response.get("access_token"), expires_at=expiration_time, key="set_access_token")
        self.cookie_manager.set("refresh_token", token_response.get("refresh_token"), expires_at=expiration_time, key="set_refresh_token")
        self.cookie_manager.set("expires_in", token_response.get("expires_in"), expires_at=expiration_time, key="set_expires_in")
        self.cookie_manager.set("token_type", token_response.get("token_type"), expires_at=expiration_time, key="set_token_type")

    def reset_credentials(self):
        print('reset_credentials')
        def delete_cookie(name: str) -> None:
            key = "delete_" + name
            if key in st.session_state:
                return
            try:
                self.cookie_manager.delete(name, key)
            except KeyError:
                print('error')
        delete_cookie("id_token")
        delete_cookie("access_token")
        delete_cookie("refresh_token")
        delete_cookie("expires_in")
        delete_cookie("token_type")

    def exchange_code_for_token(self, auth_code):
        token_params = {
            "grant_type": "authorization_code",
            "client_id": self.CLIENT_ID,
            "client_secret": self.CLIENT_SECRET,
            "code": auth_code,
            "redirect_uri": self.APP_URI
        }
        
        message = bytes(f"{self.CLIENT_ID}:{self.CLIENT_SECRET}", "utf-8")
        secret_hash = base64.b64encode(message).decode()

        headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Authorization": f"Basic {secret_hash}"
            }

        response = requests.post(self.TOKEN_ENDPOINT, data=token_params, headers=headers)
        if response.status_code == 200:
            return response.json()
        return None

    def get_user_info_from_token(self, id_token):
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
    
    def check_auth(self):
        #cookies = self.load_credentials()
        cookies = st.context.cookies
       
        # Print headers
        st.write("Headers:")
        st.json(dict(st.context.headers))

        # Print cookies
        st.write("Cookies:")
        st.json(dict(st.context.cookies))
        if 'access_token' in cookies and 'id_token' in cookies:
            print('cookieauth')
            if st.session_state.user_info:
                print('fpund in session')
                return True
            else:
                print('get from valid token')
                user_info = self.get_user_info_from_token(cookies['id_token'])

            if user_info:
                print('found in token cookie')
                st.session_state.user_info = user_info
                return True
            else:
                print('delete session cookie')
                self.reset_credentials()
                if 'user_info' in st.session_state:
                    st.session_state.user_info = None
        
        auth_code = self.get_auth_code()
        if auth_code:
            print('authcode', auth_code)
            token_response = self.exchange_code_for_token(auth_code)
            #print(token_response)
            if token_response:
                print('tokenresponse', token_response)
                user_info = self.get_user_info_from_token(token_response['id_token'])
                print('user info from id_token', user_info)
                st.session_state.user_info = user_info
                self.set_credentials(token_response)
                return True
        return False

    def logout(self):
        self.reset_credentials()
        if 'user_info' in st.session_state:
            st.session_state.user_info= None
