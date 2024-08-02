import os
import json
import hashlib
from aws_cdk import (
    NestedStack,
    RemovalPolicy,
    aws_s3 as s3,
    aws_s3_deployment as s3deploy,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_bedrock as bedrock,
    aws_ssm as ssm,
    CfnOutput,
    CustomResource
)
from constructs import Construct

class BedrockProductKnowledgeBaseStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, app_name: str, config, data_source_bucket, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        random_hash = hashlib.sha256(f"{app_name}-{self.region}".encode()).hexdigest()[:8]

        # Create the IAM role for Bedrock Knowledge Base
        product_knowledge_base_role = iam.Role(
            self, "BedrockKnowledgeBaseRole",
            role_name=f"{app_name}-{random_hash}-product-kb-role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for Bedrock Product Knowledge Base"
        )

        # Allow permission to invoke bedrock model. Make sure you have access granted to ue this foundation model.
        product_knowledge_base_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel"
            ],
            resources=[f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"]
        ))

        data_source_bucket.grant_read(product_knowledge_base_role)

        # Create Bedrock Knowledge Base
        product_catalog_knowledge_base = bedrock.CfnKnowledgeBase(
            self, "ProductCatalogKnowledgeBase",
            role_arn= product_knowledge_base_role.role_arn,
            name=f"{app_name}-product-catalog-kb",
            description="Knowledge base for product catalog",
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v1"
                )
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS"
            )
        )

        self.product_knowledge_base_id = product_catalog_knowledge_base.attr_knowledge_base_id

        # Create S3 DataSource for Product Knowledge Base
        product_catalog_data_source=bedrock.CfnDataSource(
            self, "ProductCatalogS3DataSource",
            name=f"{app_name}-product-catalog-s3-datasource",
            knowledge_base_id= self.product_knowledge_base_id,
            data_source_configuration = bedrock.CfnDataSource.DataSourceConfigurationProperty(
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=data_source_bucket.bucket_arn,
                    inclusion_prefixes=["products/"]
                ),
                type="S3"
            )
        )
        
        # Store the Product Catalog KnowledgeBaseId in SSM Parameter Store
        ssm.StringParameter(
            self, f"ProductKnowledgeBaseIdParameter",
            parameter_name=config.product_catalog_kb_id_param,
            string_value=self.product_knowledge_base_id
        )
        

        
        


