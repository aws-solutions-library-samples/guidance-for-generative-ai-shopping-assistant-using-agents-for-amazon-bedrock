# config.py
import os
import boto3
import requests
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()

        self.COGNITO_DOMAIN = os.environ.get("USER_POOL_DOMAIN","")
        self.COGNITO_CLIENT_ID = os.environ.get("USER_POOL_CLIENT_ID","")
        self.COGNITO_CLIENT_SECRET = os.environ.get("USER_POOL_CLIENT_SECRET","")
        self.REDIRECT_URI = os.environ.get("REDIRECT_URI", None)
        self.SHOPPING_AGENT_ALIAS_ID = os.environ.get("SHOPPING_AGENT_ALIAS_ID", "TSTALIASID")
        self.SHOPPING_AGENT_ID = os.environ.get("SHOPPING_AGENT_ID")
        self.API_URL = os.environ.get("API_URL")
        self.API_KEY = os.environ.get("API_KEY")
        self.AWS_ACCOUNT_ID, self.AWS_REGION, self.SESSION = self.get_aws_env_values()
        self.MODEL_INPUT_TOKEN_PRICE = 0.003 # Price per 1000 tokens
        self.MODEL_OUTPUT_TOKEN_PRICE = 0.015 # Price per 1000 tokens

    
    def get_aws_env_values(self):
        key = os.environ.get('AWS_ACCESS_KEY_ID', '')
        secret = os.environ.get('AWS_SECRET_ACCESS_KEY','')
        sessionToken = None

        credentials_relative_uri = os.environ.get('AWS_CONTAINER_CREDENTIALS_RELATIVE_URI','')
        sessionToken = None
        credentials_url = f'http://169.254.170.2{credentials_relative_uri}'
        if credentials_relative_uri != '':
            response = requests.get(credentials_url)
            response_json = response.json()
            key = response_json['AccessKeyId']
            secret = response_json['SecretAccessKey']
            sessionToken = response_json['Token']

        AWS_ACCOUNT_ID =  os.environ.get("ACCOUNT_ID")
        AWS_REGION = os.environ.get('AWS_REGION',os.environ.get('AWS_DEFAULT_REGION'))
        
        if key == '' or secret == '':
            session_kwargs = {"region_name": AWS_REGION,  "aws_session_token": sessionToken}
        else:
            session_kwargs = {"region_name": AWS_REGION, "aws_access_key_id" : key, "aws_secret_access_key" : secret, "aws_session_token": sessionToken}
        
        profile_name = os.environ.get("AWS_PROFILE")
        if profile_name:
            print(f"Using profile: {profile_name}")
            session_kwargs["profile_name"] = profile_name

        SESSION = boto3.Session(**session_kwargs)
        
        return AWS_ACCOUNT_ID, AWS_REGION, SESSION

        
