import hashlib
import os
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

class RetailShoppingAgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        random_hash = hashlib.sha256(f"{app_name}-{self.region}".encode()).hexdigest()[:8]

        # Create S3 bucket for Bedrock knowledge base data source
        data_source_bucket = s3.Bucket(
            self, "KnowledgeBaseS3DataSourceBucket",
            bucket_name=f"{app_name}-{self.region}-{random_hash}-kb",
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

        s3_upload_kb_files.node.add_dependency(data_source_bucket)
        upload_product_catalog_kb_cr.node.add_dependency(s3_upload_kb_files)
        upload_product_catalog_kb_cr.node.add_dependency(product_catalog_kb_stack)

        product_catalog_kb_stack.node.add_dependency(aoss_stack)
        product_catalog_kb_stack.node.add_dependency(data_source_bucket)
        
        shopping_agent_stack.node.add_dependency(product_catalog_kb_stack)
   
    def upload_product_catalog_and_sync_kb(self, data_source_bucket, knowledge_base_id, data_source_id, config):

        # Create Lambda function to process product catalog
        lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "lambda", "upload_product_catalog_and_sync_kb")

        process_product_catalog_lambda = lambda_.Function(
            self, "UploadAndSyncProductCatalogToKBLambda",
            function_name=f"{config.app_name}-upload-product-catalog-and-sync-kb",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset(lambda_code_path),
            environment={
                "CLOUDFRONT_URL": ssm.StringParameter.value_for_string_parameter(
                    self, config.cloudfront_url_param
                ),
                "APP_URL": ssm.StringParameter.value_for_string_parameter(
                    self, config.app_url_param
                ),
                "BUCKET_NAME": data_source_bucket.bucket_name,
                "BUCKET_PREFIX": config.product_vector_index_name,
                "KNOWLEDGE_BASE_ID": knowledge_base_id,
                "DATA_SOURCE_ID": data_source_id
            },
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
    