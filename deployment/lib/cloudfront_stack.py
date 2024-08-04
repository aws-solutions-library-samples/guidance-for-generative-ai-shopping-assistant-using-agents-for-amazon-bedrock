import os
import hashlib
from aws_cdk import (
    Stack,
    aws_s3 as s3,
    aws_cloudfront as cloudfront,
    aws_cloudfront_origins as origins,
    aws_lambda as lambda_,
    custom_resources as cr,
    aws_ssm as ssm,
    aws_iam as iam,
    RemovalPolicy,
    Duration,
    BundlingOptions,
    Size,
    CfnOutput
)
from constructs import Construct

class S3CloudFrontStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, cloudfront_url_param: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        random_hash = hashlib.sha256(f"{app_name}-{self.region}".encode()).hexdigest()[:8]
        self.app_name= app_name

        # Create S3 bucket
        self.bucket = s3.Bucket(
            self, 
            f"{app_name}-bucket",
            removal_policy=RemovalPolicy.DESTROY, # RETAIN for production to avoid deletion of bucket 
            auto_delete_objects = True, # Disable for production to avoid deletion of bucket when it is not empty
            bucket_name= f"{app_name}-{self.region}-{random_hash}"
        )

        # CloudFront Origin Access Identity
        oai = cloudfront.OriginAccessIdentity(
            self, 
            f"{app_name}-oai",
            comment=f"OAI for {app_name}'s S3 bucket"
        )

        # Grant read permissions to CloudFront OAI
        self.bucket.grant_read(oai)

        # Create logging bucket with ACLs enabled
        self.logs_bucket = s3.Bucket(
            self, 
            f"{app_name}-logs-bucket",
            removal_policy=RemovalPolicy.DESTROY, 
            auto_delete_objects = True, # Disable for production to avoid deletion of bucket when it is not empty
            object_ownership=s3.ObjectOwnership.OBJECT_WRITER,
            bucket_name= f"{app_name}-{self.region}-{random_hash}-logs-bucket",  
        )

        bucket_origin=origins.S3Origin(self.bucket, origin_access_identity=oai)
        # Create CloudFront distribution
        self.distribution = cloudfront.Distribution(
            self, 
            f"{app_name}-distribution",
            default_behavior=cloudfront.BehaviorOptions(
                origin=bucket_origin,
                viewer_protocol_policy=cloudfront.ViewerProtocolPolicy.REDIRECT_TO_HTTPS,
                allowed_methods=cloudfront.AllowedMethods.ALLOW_GET_HEAD_OPTIONS,
                cached_methods=cloudfront.CachedMethods.CACHE_GET_HEAD_OPTIONS,
                cache_policy=cloudfront.CachePolicy.CACHING_OPTIMIZED,
                origin_request_policy=cloudfront.OriginRequestPolicy.CORS_S3_ORIGIN, 
                response_headers_policy=cloudfront.ResponseHeadersPolicy.CORS_ALLOW_ALL_ORIGINS 
            ),
            minimum_protocol_version=cloudfront.SecurityPolicyProtocol.TLS_V1_2_2021,
            enable_logging=True,
            log_bucket=self.logs_bucket,
            log_file_prefix="cloudfront-access-logs/"
        )
    
        # Store the CloudFront distribution URL in SSM Parameter Store
        ssm.StringParameter(
            self, 
            f"{app_name}-cloudfront-url",
            parameter_name=f"{cloudfront_url_param}",
            string_value=f"https://{self.distribution.distribution_domain_name}",
            description="CloudFront distribution domain name"
        )

        self.upload_product_images()

        # Output the CloudFront distribution URL
        CfnOutput(self, f"{app_name}-CloudFrontURL", value=self.distribution.distribution_domain_name)

        # Output the S3 bucket name
        CfnOutput(self, f"{app_name}-S3BucketName", value=self.bucket.bucket_name)

    def upload_product_images(self):
        self.lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "lambda", "upload_product_images")
        upload_images_lambda = lambda_.Function(
            self,
            f"{self.app_name}-upload-product-images",
            function_name=f"{self.app_name}-upload-product-images",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            ephemeral_storage_size=Size.mebibytes(2048),
            code=lambda_.Code.from_asset(
                self.lambda_code_path,
                bundling= BundlingOptions(
                    image=lambda_.Runtime.PYTHON_3_9.bundling_image,
                    command=[
                        "bash", "-c",
                        "pip install --no-cache -r requirements.txt -t /asset-output && cp -rT . /asset-output"
                    ]
                ),
            ),
            environment={
                "BUCKET_NAME": self.bucket.bucket_name,
                "IMAGES_URL": "https://code.retaildemostore.retail.aws.dev/images.tar.gz"
            },
            timeout=Duration.minutes(5),
            memory_size=1024,
        )

        # Grant the Lambda function permissions to write to the S3 bucket
        self.bucket.grant_read_write(upload_images_lambda)

        # Create a unique name for the custom resource role
        unique_string = hashlib.md5(f"{self.app_name}-{self.region}".encode()).hexdigest()[:8]
        custom_resource_role_name = f"{self.app_name}-{unique_string}-upload-images-cr-role"

        # Create a role for the custom resource
        custom_resource_role = iam.Role(
            self,
            f"{self.app_name}-upload-images-custom-resource-role",
            role_name=custom_resource_role_name,
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Grant the custom resource role permission to invoke the Lambda function
        upload_images_lambda.grant_invoke(custom_resource_role)

        cr_physical_id = cr.PhysicalResourceId.of(f"{self.app_name}-upload-product-images")
        custom_resource = cr.AwsCustomResource(
            self,
            f"{self.app_name}-upload-images-custom-resource",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                physical_resource_id=cr_physical_id,
                parameters={
                    "FunctionName": upload_images_lambda.function_name,
                    "InvocationType": "Event"
                }
            ),
            # Its better to run the lambda manually from console than update on every stack deployment
            # on_update=cr.AwsSdkCall(
            #     service="Lambda",
            #     action="invoke",
            #     physical_resource_id=cr_physical_id,
            #     parameters={
            #         "FunctionName": upload_images_lambda.function_name,
            #         "InvocationType": "Event"
            #     }
            # ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[upload_images_lambda.function_arn]
                )
            ]),
            role=custom_resource_role
        )

        custom_resource.node.add_dependency(upload_images_lambda)


