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
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    RemovalPolicy,
    CfnOutput
)
from lib.config import Config

class RetailShoppingAgentStack(Stack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.unique_string = hashlib.sha256(f"{app_name}-{self.region}-{self.account}".encode(), usedforsecurity=False).hexdigest()[:8]

        # Copy products.json file to KB folder for upload to S3
        source_file = os.path.join(os.path.dirname(__file__), '..', 'data', 'products.json')
        dest_file = os.path.join(os.path.dirname(__file__), '..', 'bedrock_agent', 'knowledge_bases', 'products.json')
        shutil.copy2(source_file, dest_file)

        # Create S3 bucket for Bedrock knowledge base data source
        self.data_source_bucket = s3.Bucket(
            self, "KnowledgeBaseS3DataSourceBucket",
            bucket_name=f"{app_name}-{self.region}-{self.unique_string}-kb",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )

        # Copy KB Files to ingest
        s3_upload_kb_files = s3deploy.BucketDeployment(self, "UploadKBFiles",
            sources=[s3deploy.Source.asset("./bedrock_agent/knowledge_bases")],
            destination_bucket=self.data_source_bucket
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
            data_source_bucket = self.data_source_bucket,
            opensearch_collection_arn = aoss_stack.opensearch_collection_arn,
            opensearch_collection_name = aoss_stack.opensearch_collection_name,
            opensearch_collection_endpoint = aoss_stack.opensearch_collection_endpoint
        )
        self.knowledge_base_id = product_catalog_kb_stack.knowledge_base_id
        self.data_source_id = product_catalog_kb_stack.data_source_id

        # Create Amazon Bedrock Shopping Agent
        shopping_agent_stack = BedrockShoppingAgentStack(
            self,
            "BedrockShoppingAgentStack",
            app_name=config.app_name,
            config=config,
            product_kb_id=product_catalog_kb_stack.knowledge_base_id
        )

        # Add stack dependencies
        s3_upload_kb_files.node.add_dependency(self.data_source_bucket)

        product_catalog_kb_stack.node.add_dependency(aoss_stack)
        product_catalog_kb_stack.node.add_dependency(self.data_source_bucket)
        
        shopping_agent_stack.node.add_dependency(product_catalog_kb_stack)

        CfnOutput(self, "ProductCatalog-KnowledgeBaseId", value=product_catalog_kb_stack.knowledge_base_id)
        CfnOutput(self, "ProductCatalog-KnowledgeBaseName", value=product_catalog_kb_stack.knowledge_base_name)
        CfnOutput(self, "ShoppingAgentName", value=shopping_agent_stack.agent_name)
        CfnOutput(self, "ShoppingAgentId", value=shopping_agent_stack.agent_id)
        CfnOutput(self, "ShoppingAgentAliasId", value=shopping_agent_stack.agent_alias_id)
   
    