#!/usr/bin/env python3
import os
import aws_cdk as cdk
from lib.retail_genai_assiatant_stack import RetailGenAIAssistantStack
from lib.config import get_config


def main():

    account = os.environ.get('CDK_DEFAULT_ACCOUNT')
    region = os.environ.get('CDK_DEFAULT_REGION')
    env = cdk.Environment(account=account, region=region)

    app = cdk.App()

    config = get_config()

    RetailGenAIAssistantStack(
        app,
        "RetailAIAssistantStack",
        app_name=config.app_name,
        config=config,
        env=env
    )

    app.synth()

if __name__ == "__main__":
    main()
