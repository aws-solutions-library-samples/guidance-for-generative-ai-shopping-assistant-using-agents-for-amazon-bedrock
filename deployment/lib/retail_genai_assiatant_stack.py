from aws_cdk import Stack
from constructs import Construct
from lib.cognito_stack import CognitoStack
from lib.ecs_stack import EcsStack

class RetailGenAIAssistantStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.application_dns_name = f"{app_name}.{config.domain_name}" if hasattr(config, 'domain_name') else None

        # Create Cognito Stack
        cognito_stack = CognitoStack(
            self, 
            "CognitoStack", 
            app_name, 
            config, 
            application_dns_name=self.application_dns_name
        )

        # Create ECS Stack
        ecs_stack = EcsStack(
            self, 
            "EcsStack", 
            app_name, 
            config,
            user_pool=cognito_stack.user_pool,
            user_pool_client=cognito_stack.user_pool_client,
            user_pool_domain=cognito_stack.user_pool_domain,
            cognito_client_secret_param=cognito_stack.client_secret_param.parameter_name,
            application_dns_name=self.application_dns_name,

        )
