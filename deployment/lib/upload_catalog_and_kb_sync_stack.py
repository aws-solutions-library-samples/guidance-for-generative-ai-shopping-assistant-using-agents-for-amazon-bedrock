import os
import hashlib
from aws_cdk import (
    Stack,
    aws_lambda as lambda_,
    custom_resources as cr,
    aws_s3 as s3,
    aws_iam as iam,
    Duration
)
from constructs import Construct
from lib.config import Config

class UploadCatalogAndKBSyncStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, app_name: str, data_source_bucket: s3.IBucket, knowledge_base_id: str, data_source_id: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.unique_string = hashlib.sha256(f"{app_name}-{self.region}-{self.account}".encode()).hexdigest()[:8]

        # Create Lambda function to process product catalog
        lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "lambda", "upload_product_catalog_and_sync_kb")
        # Create a unique name for the lambda role
        lambda_role_name = f"{self.unique_string}-upload-product-catalog-role"

        # Create the IAM role for the Lambda function
        lambda_role = iam.Role(
            self, "ProductServiceLambdaRole",
            role_name= lambda_role_name,
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )

        # Grant the Lambda function permission to read from SSM Parameter Store
        lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter", "ssm:GetParameters", "ssm:GetParametersByPath"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/{config.app_name}/*"]
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

        process_product_catalog_lambda = lambda_.Function(
            self, "UploadAndSyncProductCatalogToKB",
            function_name=f"{config.app_name}-upload-product-catalog-and-sync-kb",
            role = lambda_role,
            runtime=lambda_.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            environment={
                "CLOUDFRONT_URL_PARAM": config.cloudfront_url_param,
                "APP_URL_PARAM": config.app_url_param,
                "BUCKET_NAME": data_source_bucket.bucket_name,
                "BUCKET_PREFIX": config.product_vector_index_name,
                "KNOWLEDGE_BASE_ID": knowledge_base_id,
                "DATA_SOURCE_ID": data_source_id,
                "SSM_PARAMETER_STORE_TTL" : "120" # Time to live for ssm parameter cache in seconds
            },
            params_and_secrets=params_and_secrets,
            memory_size=1024,
            timeout=Duration.minutes(5)
        )

        # Grant Lambda function read/write permissions to the S3 bucket
        data_source_bucket.grant_read_write(process_product_catalog_lambda)

        process_product_catalog_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "bedrock:StartIngestionJob"
            ],
            resources=[f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{knowledge_base_id}"]
        ))

        cr_physical_id = cr.PhysicalResourceId.of("UploadAndSyncProductCatalogToKB")
        # Create custom resource to invoke the Lambda function
        process_catalog_cr = cr.AwsCustomResource(
            self, "UploadAndSyncProductCatalogToKBCustomResource",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": process_product_catalog_lambda.function_name,
                    "InvocationType": "Event"
                },
                physical_resource_id = cr_physical_id
            ),
            # The below action will upload product files and start ingestion job on every CDK update
            # It is better to run the Lambda manually from the AWS console if needed.
            # on_update=cr.AwsSdkCall(
            #     service="Lambda",
            #     action="invoke",
            #     parameters={
            #         "FunctionName": process_product_catalog_lambda.function_name,
            #         "InvocationType": "Event"
            #     },
            #     physical_resource_id= cr_physical_id
            # ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[process_product_catalog_lambda.function_arn]
                )
            ])
        )
