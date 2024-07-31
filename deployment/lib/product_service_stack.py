import os
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    aws_apigateway as apigw,
    aws_iam as iam,
    aws_ssm as ssm,
    CfnOutput,
    Duration
)
from constructs import Construct

class ProductServiceStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, app_name: str, config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Path to your lambda function code
        lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "..", "source", "product_service")

        # Read SSM parameter
        cloudfront_url = ssm.StringParameter.value_for_string_parameter(
            self, config.cloudfront_url_param, 1
        )

        # Create the lambda function
        product_service_lambda = lambda_.Function(
            self, "ProductServiceLambda",
            runtime=lambda_.Runtime.PYTHON_3_9,
            function_name=f"{app_name}-product-service",
            handler="index.handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            timeout=Duration.seconds(30),
            memory_size=1024,
            environment={
                "CLOUDFRONT_URL": cloudfront_url,
            }
        )

        # Create an API Gateway
        api = apigw.RestApi(
            self, f"{app_name}Api",
            rest_api_name=f"{app_name}-api",
            description=f"This API serves {app_name} functionalities",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=['GET', 'OPTIONS'],
                allow_methods=apigw.Cors.ALL_METHODS,
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"],
                max_age=Duration.days(1)
            )
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
            )
        )

        # GET /products/featured
        featured = products.add_resource("featured")
        featured.add_method(
            "GET", 
            apigw.LambdaIntegration(
                product_service_lambda,
                proxy=True  # Enable proxy integration for request passthrough
            )
        )

        # Grant API Gateway permission to invoke the Lambda function
        product_service_lambda.grant_invoke(iam.ServicePrincipal("apigateway.amazonaws.com"))

        # Store the API URL in SSM Parameter Store
        ssm.StringParameter(
            self, f"{app_name}ApiGWUrl",
            parameter_name=config.apigateway_url_param,
            string_value=api.url
        )

        # Add CloudFormation output for API URL
        CfnOutput(
            self, "ProductServiceApiUrl",
            value=api.url,
            description="URL of the Product Service API",
            export_name=f"{app_name}-product-service-api-url"
        )
