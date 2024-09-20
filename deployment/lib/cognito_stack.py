# lib/cognito_stack.py
import os
import hashlib
from aws_cdk import (
    NestedStack,
    aws_cognito as cognito,
    aws_ssm as ssm,
    aws_lambda as lambda_,
    aws_iam as iam,
    custom_resources as cr,
    CfnOutput,
    RemovalPolicy
)
from lib.config import Config
from constructs import Construct

class CognitoStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, config: Config, application_dns_name: str = None, alb_dns_name : str =None, **kwargs)  -> None:
        super().__init__(scope, construct_id, **kwargs)

        unique_string = hashlib.md5(f"{app_name}-{self.region}-{self.account}".encode(), usedforsecurity=False).hexdigest()[:8]
        self.default_user_email=config.default_user_email if hasattr(config, 'default_user_email') else None
        self.default_user_name=config.default_user_name if hasattr(config, 'default_user_name') else None
        self.default_temp_password=config.default_temp_password if hasattr(config, 'default_temp_password') else None

        if application_dns_name:
            self.app_url = f"https://{application_dns_name}"
        else:
            self.app_url = f"http://{alb_dns_name}.{self.region}.elb.amazonaws.com"

        self.user_pool = cognito.UserPool(
            self,
            f"{app_name}-{unique_string}-user-pool",
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(mutable=True, required=True)
            ),
            user_pool_name=f"{app_name}-{self.region}-user-pool",
            removal_policy= RemovalPolicy.DESTROY # Comment out this to retain your users on destroy stack
        )

        self.user_pool_domain = self.user_pool.add_domain(
            f"{app_name}-{unique_string}-user-pool-domain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{app_name}-{self.region}-{unique_string}-domain"
            )
        )

        # Add localhost to test Cognito Auth locally
        callback_urls=[ "http://localhost:8501"]
        logout_urls=["http://localhost:8501"]

        # Cognito Hosted UI authentication can only be added to ECS app if custom domain is provided
        if config.domain_name:
            callback_urls=[
                f"{self.app_url}/oauth2/idpresponse", 
                self.app_url,
                "http://localhost:8501"
            ]
            logout_urls=[
                self.app_url,
                "http://localhost:8501"
            ]

        oauth_settings = cognito.OAuthSettings(
            callback_urls=callback_urls,
            logout_urls= logout_urls,
            flows=cognito.OAuthFlows(authorization_code_grant=True),
            scopes=[
                cognito.OAuthScope.OPENID,
                cognito.OAuthScope.EMAIL,
                cognito.OAuthScope.PROFILE
            ]
        )

        self.user_pool_client = self.user_pool.add_client(
            f"{app_name}-app-client",
            user_pool_client_name="AppAuthentication",
            generate_secret=True,
            auth_flows=cognito.AuthFlow(
                admin_user_password=True,
                user_srp=True,
                user_password=True
            ),
            o_auth=oauth_settings,
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ]
        )
        
        # Logout URLs and redirect URIs can't be set in CDK constructs natively ...yet
        user_pool_client_cf: cognito.CfnUserPoolClient = self.user_pool_client.node.default_child
        user_pool_client_cf.logout_ur_ls = logout_urls

        # Store cognito propoerties in Parameter Store as a simple string
        self.client_secret_param = ssm.StringParameter(
            self,
            f"{app_name}-client-secret",
            parameter_name= config.cognito_client_secret_param,
            string_value=self.user_pool_client.user_pool_client_secret.unsafe_unwrap(),
            description="Cognito User Pool Client Secret"
        )

        self.client_secret_param = ssm.StringParameter(
            self,
            f"{app_name}-client-id",
            parameter_name= config.cognito_client_id_param,
            string_value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client Id"
        )

        self.client_secret_param = ssm.StringParameter(
            self,
            f"{app_name}-user-pool-id",
            parameter_name= config.cognito_user_pool_id_param,
            string_value=self.user_pool.user_pool_id,
            description="Cognito User Pool Id"
        )

        self.client_secret_param = ssm.StringParameter(
            self,
            f"{app_name}-user-pool-domain",
            parameter_name= config.cognito_user_pool_domain_param,
            string_value=self.user_pool_domain.base_url(),
            description="Cognito User Pool Domain"
        )

        # Create demo user if default_user_email is provided
        if self.default_user_email and self.default_user_name and self.default_temp_password:
            self.create_demo_user(app_name)
            CfnOutput(self, "DemoUserName", value=self.default_user_name)
            CfnOutput(self, "UserTempPassword", value=self.default_temp_password)

        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=self.user_pool_client.user_pool_client_id)
        CfnOutput(self, "UserPoolDomain", value=self.user_pool_domain.base_url())
        CfnOutput(self, "CognitoClientSecretParam", value=self.client_secret_param.parameter_arn)

    def create_demo_user(self, app_name: str):

        lambda_code_path = os.path.join(os.path.dirname(__file__), "..",  "lambda", "create_cognito_user")
        create_user_lambda = lambda_.Function(
            self,
            "CreateCognitoUser",
            function_name=f"{app_name}-create-cognito-user",
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            environment={
                "USER_POOL_ID": self.user_pool.user_pool_id,
                "DEFAULT_USER_EMAIL": self.default_user_email,
                "DEFAULT_USER_NAME": self.default_user_name,
                "DEFAULT_TEMP_PASSWORD": self.default_temp_password,
            }
        )

        self.user_pool.grant(create_user_lambda, "cognito-idp:AdminCreateUser")
        self.user_pool.grant(create_user_lambda, "cognito-idp:AdminGetUser")
        self.user_pool.grant(create_user_lambda, "cognito-idp:AdminSetUserPassword")

        # Create a unique name for the custom resource role
        unique_string = hashlib.md5(f"{app_name}-{self.region}".encode(), usedforsecurity=False).hexdigest()[:8]
        custom_resource_role_name = f"{app_name}-{unique_string}-create-user-cr-role"

        # Create a role for the custom resource
        custom_resource_role = iam.Role(
            self,
            f"{app_name}-custom-resource-role",
            role_name= custom_resource_role_name,
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Grant the custom resource role permission to invoke the Lambda function
        create_user_lambda.grant_invoke(custom_resource_role)

        cr_physical_id = cr.PhysicalResourceId.of("CreateCognitoUser")
        cr.AwsCustomResource(
            self,
            "CreateCognitoUserCustomResource",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": create_user_lambda.function_name,
                    "InvocationType": "Event"
                },
                physical_resource_id= cr_physical_id
            ),
            on_update=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": create_user_lambda.function_name,
                    "InvocationType": "Event"
                },
                physical_resource_id= cr_physical_id
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[create_user_lambda.function_arn]
                )
            ]),
            role=custom_resource_role
        )
