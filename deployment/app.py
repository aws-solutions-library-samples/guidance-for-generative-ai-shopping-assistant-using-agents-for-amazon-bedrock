#!/usr/bin/env python3
import os
import aws_cdk as cdk
from lib.retail_ai_assiatant_stack import RetailAIAssistantStack
from lib.product_service_stack import ProductServiceStack
from lib.cloudfront_stack import S3CloudFrontStack
from lib.shopping_assistant_stack import ShoppingAssistantStack
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
        "S3CloudFrontStack", 
        app_name=config.app_name,
        cloudfront_url_param = config.cloudfront_url_param,
        env=env
    )

    retail_ai_stack = RetailAIAssistantStack(
        app,
        "RetailAIAssistantStack",
        app_name=config.app_name,
        config=config,
        env=env
    )

    product_service_stack = ProductServiceStack(
        app,
        "ProductServiceStack",
        app_name=config.app_name,
        config=config,
        env=env
    )

    shopping_agent_stack = ShoppingAssistantStack(
        app,
        "ShoppingAssistantStack",
        app_name=config.app_name,
        config=config,
        env=env
    )

    # Add dependency for cloudfront stack to use cloudfront url param 
    product_service_stack.add_dependency(cloudfront_images_stack)

    # Add dependency for cloudfront stack to use cloudfront url and api gateway url from prodyuct service stack
    retail_ai_stack.add_dependency(product_service_stack)

    app.synth()

if __name__ == "__main__":
    main()
