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

        self.product_vector_index_name="product-catalog"
        self.faq_vector_index_name="faq-policies"

        # Add the SSM param names
        self.cloudfront_url_param = f"/{self.app_name}/cloudfront-url"
        self.apigateway_url_param = f"/{self.app_name}/apigateway-url"
        self.cognitoclientsecret_param = f"/{self.app_name}/cognito-client-secret"
        self.app_url_param = ''f"/{self.app_name}/app-url"
        self.product_catalog_kb_id_param = ''f"/{self.app_name}/product-catalog-kb-id"
        self.shopping_agent_id_param = ''f"/{self.app_name}/bedrock-shopping-agent-id"
        self.shopping_agent_alias_id_param = ''f"/{self.app_name}/bedrock-shopping-agent-alias-id"
        self.opensearch_endpoint_param = ''f"/{self.app_name}/opensearch-collection-endpoint"

def get_config():
    return Config()
