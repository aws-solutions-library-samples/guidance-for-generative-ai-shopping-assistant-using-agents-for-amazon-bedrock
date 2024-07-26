# lib/cognito_stack.py
from aws_cdk import (
    NestedStack,
    aws_cognito as cognito,
    CfnOutput
)
from constructs import Construct

class CognitoStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, application_dns_name: str,  default_user_email: str = None,  **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.user_pool = cognito.UserPool(
            self,
            f"{app_name}-user-pool",
            account_recovery=cognito.AccountRecovery.EMAIL_ONLY,
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            self_sign_up_enabled=False,
            sign_in_aliases=cognito.SignInAliases(username=True, email=True),
            standard_attributes=cognito.StandardAttributes(
                email=cognito.StandardAttribute(mutable=True, required=True)
            ),
            user_pool_name=f"{app_name}-{self.region}-user-pool"
        )

        self.user_pool_domain = self.user_pool.add_domain(
            f"{app_name}-user-pool-domain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"{app_name}-{self.region}-domain"
            )
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
            o_auth=cognito.OAuthSettings(
                callback_urls=[f"https://{application_dns_name}/oauth2/idpresponse"],
                logout_urls=[f"https://{application_dns_name}"],
                flows=cognito.OAuthFlows(authorization_code_grant=True),
                scopes=[
                    cognito.OAuthScope.OPENID,
                    cognito.OAuthScope.EMAIL,
                    cognito.OAuthScope.PHONE
                ]
            ),
            supported_identity_providers=[
                cognito.UserPoolClientIdentityProvider.COGNITO
            ]
        )

        # Logout URLs and redirect URIs can't be set in CDK constructs natively ...yet
        user_pool_client_cf: cognito.CfnUserPoolClient = self.user_pool_client.node.default_child
        user_pool_client_cf.logout_ur_ls = [
            # This is here to allow a redirect to the login page
            # after the logout has been completed
            f"https://{application_dns_name}"
        ]


        # if default_user_email:
        #     cognito.CfnUserPoolUser(
        #         self,
        #         f"default-user",
        #         user_pool_id=self.user_pool.user_pool_id,
        #         username=default_user_email,
        #         user_attributes=[
        #             {"name": "email", "value": default_user_email},
        #             {"name": "email_verified", "value": "true"}
        #         ]
        #     )

        CfnOutput(self, "UserPoolId", value=self.user_pool.user_pool_id)
        CfnOutput(self, "UserPoolClientId", value=self.user_pool_client.user_pool_client_id)
        CfnOutput(self, "UserPoolDomain", value=self.user_pool_domain.base_url())
