import os
import json
import hashlib
from aws_cdk import (
    NestedStack,
    aws_opensearchserverless as opensearchserverless,
    aws_iam as iam,
    aws_lambda as lambda_,
    aws_bedrock as bedrock,
    aws_ssm as ssm,    
    custom_resources as cr,
    BundlingOptions,
    CfnOutput,
    Duration
)
from constructs import Construct

class BedrockProductKnowledgeBaseStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, app_name: str, config, data_source_bucket, 
                 opensearch_collection_arn, opensearch_collection_name, opensearch_collection_endpoint, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.app_name= app_name
        self.random_hash = hashlib.sha256(f"{self.app_name}-{self.region}".encode()).hexdigest()[:8]

        index_name = config.product_vector_index_name
        vector_field = 'product-details'
        text_field="textField"
        metadata_field="metadataField"
        embeddings_model_id='amazon.titan-embed-text-v1'
        vector_dimension = 1536 # For Titan text embedding v1. 

        # Create the IAM role for Bedrock Knowledge Base
        self.product_knowledge_base_role = iam.Role(
            self, "BedrockKnowledgeBaseRole",
            role_name=f"{self.app_name}-{self.random_hash}-product-kb-role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            path="/service-role/",
            description="IAM role for Bedrock Product Knowledge Base"
        )

        # Allow permission to invoke bedrock model. Make sure you have access granted to ue this foundation model.
        self.product_knowledge_base_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel"
            ],
            resources=[f"arn:aws:bedrock:{self.region}::foundation-model/{embeddings_model_id}"]
        ))
       
        # Allow permission to access objects in Amazon S3 data source.
        data_source_bucket.grant_read(self.product_knowledge_base_role)
        
        # Allow permission to access data in Opensearch vector store and call Api.
        data_access_policy = self.add_aoss_access_policiy(opensearch_collection_arn, opensearch_collection_name, index_name, self.product_knowledge_base_role)

        # Create vector index in Opensearch collection
        aoss_index = self.create_vector_index(opensearch_collection_arn, opensearch_collection_name, opensearch_collection_endpoint, 
                                              index_name, vector_field, vector_dimension, text_field, metadata_field)

        # Create Bedrock Knowledge Base
        product_catalog_knowledge_base = bedrock.CfnKnowledgeBase(
            self, "ProductCatalogKnowledgeBase",
            role_arn= self.product_knowledge_base_role.role_arn,
            name=f"{self.app_name}-product-catalog-kb",
            description="Knowledge base for product catalog",
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v1"
                )
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=opensearch_collection_arn,
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        # metadata_field="AMAZON_BEDROCK_METADATA",
                        # text_field="AMAZON_BEDROCK_TEXT_CHUNK",
                        text_field=text_field,
                        metadata_field= metadata_field,
                        vector_field= vector_field
                    ),
                    vector_index_name= index_name
                )
            )
        )

        self.knowledge_base_id = product_catalog_knowledge_base.attr_knowledge_base_id

        # Add trust relationship to Knowledge Base Role
        policy = self.product_knowledge_base_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("bedrock.amazonaws.com")],
                actions=["sts:AssumeRole"],
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"AWS:SourceArn": f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/*"}
                }
            )
        )

        # Create S3 DataSource for Product Knowledge Base
        product_catalog_data_source=bedrock.CfnDataSource(
            self, "ProductCatalogS3DataSource",
            name=f"{self.app_name}-product-catalog-s3-datasource",
            knowledge_base_id= self.knowledge_base_id,
            data_source_configuration = bedrock.CfnDataSource.DataSourceConfigurationProperty(
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=data_source_bucket.bucket_arn,
                    inclusion_prefixes=[f"{index_name}/"]
                ),
                type="S3"
            ),
            data_deletion_policy= 'RETAIN'
        )
        self.data_source_id = product_catalog_data_source.attr_data_source_id

        aoss_index.node.add_dependency(data_access_policy)
        product_catalog_knowledge_base.node.add_dependency(aoss_index)
        product_catalog_data_source.node.add_dependency(product_catalog_knowledge_base)
        
        # Store the Product Catalog KnowledgeBaseId in SSM Parameter Store
        ssm.StringParameter(
            self, f"ProductKnowledgeBaseIdParameter",
            parameter_name=config.product_catalog_kb_id_param,
            string_value=self.knowledge_base_id
        )

        # Output the KB details
        CfnOutput(self, f"{product_catalog_knowledge_base.name}-id", value=self.knowledge_base_id)

    def add_aoss_access_policiy(self, opensearch_collection_arn, opensearch_collection_name, index_name, iam_role):
        
        # Allow permission to call api for opensearch collection.
        iam_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "aoss:APIAccessAll"
            ],
            resources=[opensearch_collection_arn]
        ))

        # Create data access policy for the collection
        data_access_policy = opensearchserverless.CfnAccessPolicy(
            self, f"CollectionDataAccessPolicy-{index_name}",
            name=f"{index_name}-kb-{self.random_hash}",
            description="Data access policy for Amazon Bedrock Knowledge Base collection",
            policy=json.dumps([{
                "Description": "Allow access to the collection and Indexes",
                "Rules": [
                    {
                        "ResourceType": "index",
                        "Resource": [f"index/{opensearch_collection_name}/*"],
                        "Permission": [
                            "aoss:CreateIndex",
                            "aoss:UpdateIndex",
                            "aoss:DescribeIndex",
                            "aoss:ReadDocument",
                            "aoss:WriteDocument"
                        ]
                    },
                    {
                        "ResourceType": "collection",
                        "Resource": [f"collection/{opensearch_collection_name}"],
                        "Permission": [
                            "aoss:CreateCollectionItems",
                            "aoss:UpdateCollectionItems",
                            "aoss:DescribeCollectionItems"
                        ]
                    }
                ],
                "Principal": [
                    iam_role.role_arn
                ]  
            }]),
            type="data"
        )

        return data_access_policy
    
    def create_vector_index(self, opensearch_collection_arn, opensearch_collection_name, opensearch_collection_endpoint, 
                            index_name, vector_field, vector_dimension, text_field, metadata_field):

        lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "lambda", "create_opensearch_index")

        # Create Lambda function to create OpenSearch index
        create_index_lambda = lambda_.Function(
            self,
            f"{self.app_name}-create-opensearch-index",
            function_name=f"{self.app_name}-create-opensearch-index",
            runtime=lambda_.Runtime.PYTHON_3_9,
            handler="index.handler",
            code=lambda_.Code.from_asset(
                lambda_code_path,
                    bundling= BundlingOptions(
                        image=lambda_.Runtime.PYTHON_3_9.bundling_image,
                        command=[
                            "bash", "-c",
                            "pip install --no-cache -r requirements.txt -t /asset-output && cp -rT . /asset-output"
                        ]
                    ),
                ), 
            environment={
                "INDEX_NAME": index_name,
                "AOSS_ENDPOINT": opensearch_collection_endpoint,
                "VECTOR_FIELD": vector_field,
                "TEXT_FIELD": text_field,
                "METADATA_FIELD": metadata_field,
                "VECTOR_DIMENSION": str(vector_dimension)
            },
            timeout=Duration.seconds(30)
        )

 	    # Grant the Lambda function permissions to access OpenSearch
        create_index_lambda.add_to_role_policy(iam.PolicyStatement(
            actions=[
                "aoss:CreateIndex",
                "aoss:UpdateIndex",
                "aoss:DescribeIndex"
            ],
            resources=[opensearch_collection_arn]
        ))
        aoss_data_access_policy_lambda = self.add_aoss_access_policiy( opensearch_collection_arn, opensearch_collection_name, 'index-cr', create_index_lambda.role) 

        # Create custom resource to create OpenSearch index
        cr_physical_id = cr.PhysicalResourceId.of("CreateOpenSearchIndex")
        create_index_cr = cr.AwsCustomResource(
            self, "CreateOpenSearchIndexCustomResource",
            on_create=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": create_index_lambda.function_name,
                    "InvocationType": "RequestResponse"
                },
                physical_resource_id= cr_physical_id
            ),
            on_update=cr.AwsSdkCall(
                service="Lambda",
                action="invoke",
                parameters={
                    "FunctionName": create_index_lambda.function_name,
                    "InvocationType": "RequestResponse"
                },
                physical_resource_id= cr_physical_id
            ),
            policy=cr.AwsCustomResourcePolicy.from_statements([
                iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[create_index_lambda.function_arn]
                )
            ])
        )

        create_index_cr.node.add_dependency(aoss_data_access_policy_lambda)

        return create_index_cr

    
    
        

        
        


