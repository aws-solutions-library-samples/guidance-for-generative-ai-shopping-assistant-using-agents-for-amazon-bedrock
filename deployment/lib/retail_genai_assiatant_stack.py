from aws_cdk import Stack
from constructs import Construct
from lib.cognito_stack import CognitoStack
from lib.ecs_stack import EcsStack

class RetailGenAIAssistantStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        if config.domain_name:
            application_dns_name = f"{app_name}.{config.domain_name}"

            # Create Cognito Stack
            cognito_stack = CognitoStack(self, "CognitoStack", app_name, application_dns_name, config.default_user_email)
            
            # Create ECS Stack with Cognito Pool
            ecs_stack = EcsStack(self, "EcsStack", app_name, config, cognito_stack.user_pool, cognito_stack.user_pool_client, cognito_stack.user_pool_domain, application_dns_name)
        else:
             # Create ECS Stack without Authentication
            ecs_stack = EcsStack(self, "EcsStack", app_name, config)
