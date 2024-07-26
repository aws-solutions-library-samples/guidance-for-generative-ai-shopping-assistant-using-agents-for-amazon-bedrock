import os

class Config:
    def __init__(self):
        self.number_of_tasks = 1
        self.domain_name = os.environ.get('DOMAIN_NAME') # Your custom domain in Hosted Zone
        self.hosted_zone_id = os.environ.get('HOSTED_ZONE_ID') # Your Route 53 Hosted Zone ID if exists
        self.default_user_email = os.environ.get('DEFAULT_USER_EMAIL') # Default user email for Cognito User Pool

def get_config():
    return Config()
