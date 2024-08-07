import hashlib
import os
import shutil
from constructs import Construct
from lib.bedrock_shopping_agent_stack import BedrockShoppingAgentStack
from lib.bedrock_product_kb_stack import BedrockProductKnowledgeBaseStack
from lib.opensearch_serverless_stack import OpenSearchServerlessStack
from lib.bedrock_logging_setup import BedrockLoggingStack
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    custom_resources as cr,
    aws_lambda as lambda_,
    aws_ssm as ssm,
    RemovalPolicy,
    Duration,
)
from lib.config import Config

class RetailShoppingAgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.random_hash = hashlib.sha256(f"{app_name}-{self.region}".encode()).hexdigest()[:8]

        # Copy products.json file to KB folder for upload to S3
        source_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'products.json')
        dest_file = os.path.join(os.path.dirname(__file__), '..', 'bedrock_agent', 'knowledge_bases', 'products.json')
        shutil.copy2(source_file, dest_file)

        # Create S3 bucket for Bedrock knowledge base data source
        data_source_bucket = s3.Bucket(
            self, "KnowledgeBaseS3DataSourceBucket",
            bucket_name=f"{app_name}-{self.region}-{self.random_hash}-kb",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Copy KB Files to ingest
        s3_upload_kb_files = s3deploy.BucketDeployment(self, "UploadKBFiles",
            sources=[s3deploy.Source.asset("./bedrock_agent/knowledge_bases")],
            destination_bucket=data_source_bucket
        )

        # Setup Logging for Amazon Bedrock Model Invocations for current AWS Account and Region
        model_invocation_logs = BedrockLoggingStack(
            self,
            "BedrockLoggingStack",
            config=config
        )

        # Create OpenSearchServerless vector store for Bedrock Knowledge Base
        aoss_stack = OpenSearchServerlessStack(
            self,
            "OpenSearchServerlessStack",
            app_name=config.app_name,
            config=config
        )

        # Create Product Catalog Bedrock Knowledge Base for vector search
        product_catalog_kb_stack = BedrockProductKnowledgeBaseStack(
            self,
            "BedrockProductKnowledgeBaseStack",
            app_name=config.app_name,
            config=config,
            data_source_bucket = data_source_bucket,
            opensearch_collection_arn = aoss_stack.opensearch_collection_arn,
            opensearch_collection_name = aoss_stack.opensearch_collection_name,
            opensearch_collection_endpoint = aoss_stack.opensearch_collection_endpoint
        )

        # Create Amazon Bedrock Shopping Agent
        shopping_agent_stack = BedrockShoppingAgentStack(
            self,
            "BedrockShoppingAgentStack",
            app_name=config.app_name,
            config=config,
            product_kb_id=product_catalog_kb_stack.knowledge_base_id
        )

        upload_product_catalog_kb_cr = self.upload_product_catalog_and_sync_kb(data_source_bucket, product_catalog_kb_stack.knowledge_base_id, product_catalog_kb_stack.data_source_id, config)

        # Add stack dependencies
        s3_upload_kb_files.node.add_dependency(data_source_bucket)

        upload_product_catalog_kb_cr.node.add_dependency(s3_upload_kb_files)
        upload_product_catalog_kb_cr.node.add_dependency(product_catalog_kb_stack)

        product_catalog_kb_stack.node.add_dependency(aoss_stack)
        product_catalog_kb_stack.node.add_dependency(data_source_bucket)
        
        shopping_agent_stack.node.add_dependency(product_catalog_kb_stack)
   
    def upload_product_catalog_and_sync_kb(self, data_source_bucket, knowledge_base_id, data_source_id, config):

        # Create Lambda function to process product catalog
        lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "lambda", "upload_product_catalog_and_sync_kb")
        # Create a unique name for the lambda role
        lambda_role_name = f"{self.random_hash}-upload-product-catalog-role"

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
            # Enable Lambda Extension Layer for reading SSM Parameter and Secrets from local cache
            # Update ARN based on region & architecture here: https://docs.aws.amazon.com/systems-manager/latest/userguide/ps-integration-lambda-extensions.html
            layers=[lambda_.LayerVersion.from_layer_version_arn(
                self, "ParamterStoreLambdaExtensionLayer",
                layer_version_arn="arn:aws:lambda:us-west-2:345057560386:layer:AWS-Parameters-and-Secrets-Lambda-Extension:11"
            )],
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
            on_update=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": process_product_catalog_lambda.function_name,
                    "InvocationType": "Event"
                },
                physical_resource_id= cr_physical_id
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[process_product_catalog_lambda.function_arn]
                )
            ])
        )

        return process_catalog_cr
    