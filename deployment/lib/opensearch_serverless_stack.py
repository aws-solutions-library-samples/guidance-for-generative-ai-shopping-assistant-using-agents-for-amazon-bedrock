import hashlib
import json
from aws_cdk import (
    NestedStack,
    aws_opensearchserverless as opensearchserverless,
    aws_ssm as ssm,
    aws_iam as iam,
    CfnOutput
)
from constructs import Construct

class OpenSearchServerlessStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, app_name: str, config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        random_hash = hashlib.sha256(f"{app_name}-{self.region}".encode()).hexdigest()[:8]
        self.opensearch_collection_name = f"{app_name}-kb-{random_hash}"
        
        # Create network policy for the collection with public access
        network_policy = opensearchserverless.CfnSecurityPolicy(
            self, "CollectionNetworkPolicy",
            name=f"{self.opensearch_collection_name}",
            type="network",
            description="Network policy for Amazon Bedrock Knowledge Base collection",
            policy=json.dumps([{
                "Description": "Allow newtwork access for the collection",
                "Rules": [
                    {
                        "ResourceType": "dashboard",
                        "Resource": [f"collection/{self.opensearch_collection_name}"]
                    },
                    {
                        "ResourceType": "collection",
                        "Resource": [f"collection/{self.opensearch_collection_name}"]
                    }
                ],
                "AllowFromPublic": True
            }])
        )

        # Create the encryption security policy
        encryption_sec_policy = opensearchserverless.CfnSecurityPolicy(
            self, 'CollectionEncryptionSecPolicy',
            name=f"{self.opensearch_collection_name}",
            description="Encryption policy for Amazon Bedrock Knowledge Base collection",
            type="encryption",
            policy=json.dumps({
                "Rules": [
                    {
                        "Resource": [
                            f"collection/{self.opensearch_collection_name}"
                        ],
                        "ResourceType": "collection"
                    }
                ],
                "AWSOwnedKey": True
            })
        )

        # Create OpenSearch Serverless Collection
        opensearch_collection = opensearchserverless.CfnCollection(
            self, "BedrockKnowledgeBaseCollection",
            name=f"{self.opensearch_collection_name}",
            description="Vector store for Bedrock Knowledge Base",
            type="VECTORSEARCH"
        )
        self.opensearch_collection_arn = opensearch_collection.attr_arn
        self.opensearch_collection_endpoint = opensearch_collection.attr_collection_endpoint

        opensearch_collection.node.add_dependency(network_policy)
        opensearch_collection.node.add_dependency(encryption_sec_policy)

        # Store the OpenSearch Endpoint in Parameter Store
        ssm.StringParameter(
            self, f"OpenSearchCollectionEndpointParameter",
            parameter_name=config.opensearch_endpoint_param,
            string_value=self.opensearch_collection_endpoint
        )
        
        # Output the collection details
        CfnOutput(self, f"{app_name}-opensearch-collection-arn", value=self.opensearch_collection_arn)
        CfnOutput(self, f"{app_name}-opensearch-collection-endpoint", value=self.opensearch_collection_endpoint)


        