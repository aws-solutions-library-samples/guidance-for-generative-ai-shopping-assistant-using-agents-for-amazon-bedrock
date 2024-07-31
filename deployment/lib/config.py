import os

class Config:
    def __init__(self):
        self.app_name= 'retail-ai-assistant'
        self.number_of_tasks = 1
        self.domain_name = os.environ.get('DOMAIN_NAME') # Your custom domain in Hosted Zone
        self.hosted_zone_id = os.environ.get('HOSTED_ZONE_ID') # Your Route 53 Hosted Zone ID if exists
        self.default_user_name  = 'demo-user'
        self.default_user_email = 'demo-user@example.com'
        self.default_temp_password = 'TempPass123@'

        # Add the SSM param names
        self.cloudfront_url_param = f"/{self.app_name}/cloudfront-url"
        self.apigateway_url_param = f"/{self.app_name}/apigateway-url"
        self.cognitoclientsecret_param = f"/{self.app_name}/cognito-client-secret"
        self.app_url_param = ''f"/{self.app_name}/app-url"

def get_config():
    return Config()
