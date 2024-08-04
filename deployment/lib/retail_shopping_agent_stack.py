import hashlib
import json
from constructs import Construct
from lib.bedrock_shopping_agent_stack import BedrockShoppingAgentStack
from lib.bedrock_product_kb_stack import BedrockProductKnowledgeBaseStack
from lib.opensearch_serverless_stack import OpenSearchServerlessStack
from aws_cdk import (
    Stack,
    aws_iam as iam,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    custom_resources as cr,
    RemovalPolicy
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
        s3deploy.BucketDeployment(self, "UploadKBFiles",
            sources=[s3deploy.Source.asset("./bedrock_agent/knowledge_bases")],
            destination_bucket=data_source_bucket
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
            product_kb_id=product_catalog_kb_stack.product_knowledge_base_id
        )

        product_catalog_kb_stack.node.add_dependency(aoss_stack)
        product_catalog_kb_stack.node.add_dependency(data_source_bucket)
        
        shopping_agent_stack.node.add_dependency(product_catalog_kb_stack)
    
   

        