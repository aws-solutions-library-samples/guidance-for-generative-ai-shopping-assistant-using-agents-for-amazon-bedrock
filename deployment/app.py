#!/usr/bin/env python3
import os
import aws_cdk as cdk
from lib.retail_ai_assiatant_stack import RetailGenAIAssistantStack
from lib.product_service_stack import ProductServiceStack
from lib.config import get_config


def main():

    account = os.environ.get('CDK_DEFAULT_ACCOUNT')
    region = os.environ.get('CDK_DEFAULT_REGION')
    env = cdk.Environment(account=account, region=region)

    app = cdk.App()

    config = get_config()

    retail_ai_stack = RetailGenAIAssistantStack(
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

    # Add dependency
    #product_service_stack.add_dependency(retail_ai_stack)

    app.synth()

if __name__ == "__main__":
    main()
