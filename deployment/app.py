#!/usr/bin/env python3
import os
import aws_cdk as cdk
from lib.retail_app_ai_assiatant_stack import RetailAppAIAssistantStack
from lib.product_service_stack import ProductServiceStack
from lib.cloudfront_stack import S3CloudFrontStack
from lib.retail_shopping_agent_stack import RetailShoppingAgentStack
from lib.upload_catalog_and_kb_sync_stack import UploadCatalogAndKBSyncStack
from lib.config import get_config


def main():

    account = os.environ.get('CDK_DEFAULT_ACCOUNT')
    region = os.environ.get('CDK_DEFAULT_REGION')
    env = cdk.Environment(account=account, region=region)

    app = cdk.App()

    config = get_config()

    # Create Cloudfront S3 Stack and upload images
    cloudfront_images_stack = S3CloudFrontStack(
        app,
        f"{config.app_name}S3CloudFrontStack", 
        app_name=config.app_name,
        cloudfront_url_param = config.cloudfront_url_param,
        env=env,
        description='Guidance for Generative AI Shopping Assistant using Agents for Amazon Bedrock (SO9539)'
    )

    # Create Product Service API with AWS Lambda and API Gateway
    product_service_stack = ProductServiceStack(
        app,
        f"{config.app_name}ProductServiceStack",
        app_name=config.app_name,
        config=config,
        env=env,
        description='Guidance for Generative AI Shopping Assistant using Agents for Amazon Bedrock (SO9539)'
    )

    # Create Cognito Authenticated Streamlit Web App on ECS Fargate
    retail_ai_stack = RetailAppAIAssistantStack(
        app,
        f"{config.app_name}AppStack",
        app_name=config.app_name,
        config=config,
        env=env,
        description='Guidance for Generative AI Shopping Assistant using Agents for Amazon Bedrock (SO9539)'
    )

    # Create Bedrock Agent for Shopping Assistant with Knowledge Base and Action Group
    shopping_agent_stack = RetailShoppingAgentStack(
        app,
        f"{config.app_name}ShoppingAgentStack",
        app_name=config.app_name,
        config=config,
        env=env,
        description='Guidance for Generative AI Shopping Assistant using Agents for Amazon Bedrock (SO9539)'
    )

    # Upload Product details to S3 bucket and start ingestion to Knowledge Base
    upload_catalog_and_kb_sync_stack = UploadCatalogAndKBSyncStack(
        app,
        f"{config.app_name}UploadCatalogAndKBSyncStack",
        app_name=config.app_name,
        data_source_bucket = shopping_agent_stack.data_source_bucket,
        knowledge_base_id =shopping_agent_stack.knowledge_base_id,
        data_source_id =shopping_agent_stack.data_source_id,
        config=config,
        env=env,
        description='Guidance for Generative AI Shopping Assistant using Agents for Amazon Bedrock (SO9539)'
    )

    # Add dependency to product service for cloudfront stack to use cloudfront url 
    product_service_stack.add_dependency(cloudfront_images_stack)
    
    # Add dependency to app to use cloudfront url, api gateway url and agent details 
    retail_ai_stack.add_dependency(cloudfront_images_stack)
    retail_ai_stack.add_dependency(product_service_stack)
    retail_ai_stack.add_dependency(shopping_agent_stack)

    # Add dependency to upload & sync lambda to use kb details, cloudfront url for images and app url for product details ingestion in KB
    upload_catalog_and_kb_sync_stack.node.add_dependency(shopping_agent_stack)
    upload_catalog_and_kb_sync_stack.node.add_dependency(retail_ai_stack)
    upload_catalog_and_kb_sync_stack.node.add_dependency(cloudfront_images_stack)
    

    app.synth()

if __name__ == "__main__":
    main()
