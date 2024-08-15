import os
from dotenv import load_dotenv

class Config:
    def __init__(self):
        load_dotenv()

        self.app_name= 'retail-ai-assistant' # Your AppName
        self.number_of_ecs_tasks = 1

        # Amazon Cognito settings
        self.domain_name = os.environ.get('HOSTED_ZONE_NAME') # Your Route 53 Hosted Zone domain name if exists
        self.hosted_zone_id = os.environ.get('HOSTED_ZONE_ID') # Your Route 53 Hosted Zone ID if exists
        self.default_user_name  = 'demo-user'
        self.default_user_email = 'demo-user@example.com'
        self.default_temp_password = 'TempPass123@'

        # Amazon Bedrock config names
        self.bedrock_shopping_agent_name = f"{self.app_name}-shopping-agent"
        self.bedrock_shopping_agent_alias = "PROD"
        self.product_vector_index_name="product-catalog"
        self.faq_vector_index_name="faq-policies"
        self.bedrock_agent_tags = {'AppName':f'{self.app_name}'}

        # Add the SSM param names keys
        self.cloudfront_url_param = f"/{self.app_name}/cloudfront/url"
        self.product_service_url_param = f"/{self.app_name}/product-service/api-url"
        self.product_service_apikey_secret = f"/{self.app_name}/product-service/api-key"

        self.cognito_client_secret_param = f"/{self.app_name}/cognito/client-secret"
        self.cognito_client_id_param = f"/{self.app_name}/cognito/client-id"
        self.cognito_user_pool_id_param = f"/{self.app_name}/cognito/user-pool-id"
        self.cognito_user_pool_domain_param = f"/{self.app_name}/cognito/user-pool-domain"

        self.app_url_param = f"/{self.app_name}/app-url"
        self.product_catalog_kb_id_param = f"/{self.app_name}/bedrock/product-catalog-kb-id"
        self.shopping_agent_id_param = f"/{self.app_name}/bedrock/shopping-agent-id"
        self.shopping_agent_alias_id_param = f"/{self.app_name}/bedrock/shopping-agent-alias-id"
        self.opensearch_endpoint_param = f"/{self.app_name}/opensearch/collection-endpoint"

def get_config():
    return Config()
