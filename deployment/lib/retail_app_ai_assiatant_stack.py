import hashlib
from aws_cdk import Stack
from constructs import Construct
from lib.cognito_stack import CognitoStack
from lib.ecs_app_stack import EcsAppStack
from lib.config import Config

class RetailAppAIAssistantStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)
        
        random_hash = hashlib.sha256(f"{config.app_name}-{self.region}".encode()).hexdigest()[:8]

        self.application_dns_name = f"{app_name}.{config.domain_name}" if hasattr(config, 'domain_name') else None
        self.alb_dns_name = f"{app_name}-{random_hash}"

        self.cloudfront_url_param= config.cloudfront_url_param

        # Create Cognito Stack
        cognito_stack = CognitoStack(
            self, 
            "CognitoStack", 
            app_name, 
            config, 
            application_dns_name=self.application_dns_name,
            alb_dns_name = self.alb_dns_name 
        )

        # Create ECS Stack
        ecs_stack = EcsAppStack(
            self, 
            "EcsStack", 
            app_name, 
            config,
            user_pool=cognito_stack.user_pool,
            user_pool_client=cognito_stack.user_pool_client,
            user_pool_domain=cognito_stack.user_pool_domain,
            application_dns_name=self.application_dns_name,
            alb_dns_name = self.alb_dns_name 
        )
