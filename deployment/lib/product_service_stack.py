import os
import hashlib
import json
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_lambda as lambda_,
    aws_logs as logs,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_secretsmanager as secretsmanager,
    CfnOutput,
    RemovalPolicy,
    Duration
)
from constructs import Construct
from lib.config import Config

class ProductServiceStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, app_name: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Path to your lambda function code
        lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "..", "source", "product_service")
        unique_string = hashlib.md5(f"{app_name}-{self.region}-{self.account}".encode()).hexdigest()[:8]

        # Create S3 bucket for storing application data
        self.app_data_bucket = s3.Bucket(
            self, 
            f"{app_name}DataBucket",
            removal_policy=RemovalPolicy.DESTROY, # RETAIN for production to avoid deletion of bucket 
            auto_delete_objects = True, # Disable for production to avoid deletion of bucket when it is not empty
            bucket_name= f"{app_name}-{self.region}-{unique_string}-data"
        )

        # Upload products.json to the S3 bucket
        s3deploy.BucketDeployment(
            self, "DeployProducts",
            sources=[s3deploy.Source.asset("./data")],
            destination_bucket= self.app_data_bucket,
        )

        # Create a unique name for the lambda role
        lambda_role_name = f"{app_name}-{unique_string}-product-service-role"

        # Create the IAM role for the Lambda function
        lambda_role = iam.Role(
            self, "ProductServiceLambdaRole",
            role_name= lambda_role_name,
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Grant the Lambda function permission to read app parameters from SSM Parameter Store
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/{app_name}/*"]
        ))

        # Grant the Lambda function permission to put logs in CloudWatch
        lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )

        # Enable Lambda Extension Layer for reading SSM Parameter and Secrets from local cache
        params_and_secrets = lambda_.ParamsAndSecretsLayerVersion.from_version(lambda_.ParamsAndSecretsVersions.V1_0_103,
            cache_size=500,
            log_level=lambda_.ParamsAndSecretsLogLevel.DEBUG
        )

        # Create the lambda function
        product_service_lambda = lambda_.Function(
            self, "ProductServiceLambda",
            runtime=lambda_.Runtime.PYTHON_3_12,
            function_name=f"{app_name}-product-service",
            role= lambda_role,
            handler="index.handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=1024,
            environment={
                "CLOUDFRONT_URL_PARAM": config.cloudfront_url_param,
                "APP_URL_PARAM": config.app_url_param,
                "BUCKET_NAME": self.app_data_bucket.bucket_name,
                "SSM_PARAMETER_STORE_TTL" : "120" # Time to live for ssm parameter cache in seconds
            },
            params_and_secrets= params_and_secrets
        )

        # Grant read access to S3 Bucket
        self.app_data_bucket.grant_read(product_service_lambda)

        # Create a CloudWatch log group for API Gateway
        api_log_group = logs.LogGroup(self, f"{app_name}-api-logs",
            log_group_name=f"/aws/apigateway/{app_name}-logs",
            retention=logs.RetentionDays.ONE_MONTH,  
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create an API Gateway
        api = apigw.RestApi(
            self, f"{app_name}Api",
            rest_api_name=f"{app_name}-api",
            description=f"This API serves {app_name} functionalities",
            cloud_watch_role  = True,
            cloud_watch_role_removal_policy = RemovalPolicy.DESTROY, 
            deploy_options=apigw.StageOptions(
                stage_name="prod",  
                logging_level=apigw.MethodLoggingLevel.INFO,  
                data_trace_enabled=True,
                access_log_destination=apigw.LogGroupLogDestination(api_log_group),
                access_log_format=apigw.AccessLogFormat.clf()  
            ),
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=['GET', 'OPTIONS'],
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"],
                max_age=Duration.days(1)
            )
        )

        # Store the API Key in Secrets Manager
        self.api_key_secret = secretsmanager.Secret(self, f"{app_name}-product-service-api-key-secret",
            secret_name=config.product_service_apikey_secret,
            description=f"API Key for {app_name}",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template=json.dumps({"api_key": f"{app_name}-product-service-api-key"}),
                generate_string_key="api_key"
            )
        )

        # Create an API Key
        api_key = api.add_api_key(f"{app_name}-product-service-api-key",
            api_key_name=f"{app_name}-product-service-api-key",
            value= self.api_key_secret.secret_value.unsafe_unwrap()
        )

        # Create a usage plan
        plan = api.add_usage_plan(f"{app_name}-usage-plan",
            name=f"{app_name}-usage-plan",
            throttle=apigw.ThrottleSettings(
                rate_limit=10,
                burst_limit=2
            )
        )
        
        api_key.node.add_dependency( self.api_key_secret)
        plan.node.add_dependency(api_key)

        # Associate the API Key with the usage plan
        plan.add_api_key(api_key)

        # Add the API to the usage plan
        plan.add_api_stage(
            stage=api.deployment_stage
        )

        # Create API Gateway resources and methods
        products = api.root.add_resource("products")

        # GET /products/id/{productId}
        product_id = products.add_resource("id").add_resource("{productId}")
        product_id.add_method(
            "GET", 
            apigw.LambdaIntegration(
                product_service_lambda,
                proxy=True  # Enable proxy integration for request passthrough
            ),
            api_key_required=True
        )

        # GET /products/featured
        featured = products.add_resource("featured")
        featured.add_method(
            "GET", 
            apigw.LambdaIntegration(
                product_service_lambda,
                proxy=True  # Enable proxy integration for request passthrough
            ),
            api_key_required=True
        )

        # Grant API Gateway permission to invoke the Lambda function
        product_service_lambda.grant_invoke(iam.ServicePrincipal("apigateway.amazonaws.com"))

        # Store the API URL in SSM Parameter Store
        ssm.StringParameter(
            self, f"{app_name}ApiGWUrl",
            parameter_name=config.product_service_url_param,
            string_value=api.url
        )

        # Add CloudFormation output for API URL
        CfnOutput(
            self, "ProductServiceApiUrl",
            value=api.url,
            description="URL of the Product Service API",
            export_name=f"{app_name}-product-service-api-url"
        )

        # Add CloudFormation output for S3 bucket
        CfnOutput(
            self, "{app_name}DataBucketName",
            value=self.app_data_bucket.bucket_name,
            description="Name of the S3 bucket containing app data including products",
            export_name=f"{app_name}-data-bucket-name"
        )

        # Output the Secret ARN
        CfnOutput(self, "ProductServiceApiKeySecretArn", 
                  value= self.api_key_secret.secret_arn, 
                  description="Secret ARN for Product Service API Key")
