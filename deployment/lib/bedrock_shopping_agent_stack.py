import os
import hashlib
from aws_cdk import (
    NestedStack,
    Duration,
    aws_lambda as _lambda,
    aws_iam as iam,
    aws_ssm as ssm,
    aws_bedrock as bedrock,
    CfnOutput
)
from constructs import Construct
from lib.config import Config

class BedrockShoppingAgentStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, app_name: str, config: Config, product_kb_id, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        random_hash = hashlib.sha256(f"{app_name}-{self.region}".encode()).hexdigest()[:8]

        shopping_agent_path = os.path.join(os.path.dirname(__file__), "..", "bedrock_agent", "shopping_agent")

        # Read orchestration advanced prompt 
        with open(f"{shopping_agent_path}/prompt_templates/orchestration_template.txt") as f:
            orchestration_prompt = f.read()
        
        # Read knowledge base response generation advanced prompt 
        with open(f"{shopping_agent_path}/prompt_templates/kb_response_generation_template.txt") as f:
            kb_prompt = f.read()

        # Read agent instructions
        with open(f"{shopping_agent_path}/shopping_agent_instructions.txt") as f:
            agent_instruction = f.read()

        # Read action group schema
        with open(f"{shopping_agent_path}/action_groups/create_order_actions/api_schema/create_order_actions.openapi.json") as f:
            create_order_schema = f.read()
            
        # Path to your lambda function code
        lambda_code_path = os.path.join(os.path.dirname(__file__), "..", "bedrock_agent", "shopping_agent", "action_groups" , "create_order_actions", "lambda")
        # Create the IAM role for the Lambda function
        create_order_lambda_role = iam.Role(
            self, "CreateOrderLambdaRole",
            role_name= f"{random_hash}-createorder-actions-role",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com")
        )
        # Grant the Lambda function permission to read from SSM Parameter Store
        create_order_lambda_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/{config.app_name}/*"]
        ))

        # Grant the Lambda function permission to put logs in CloudWatch
        create_order_lambda_role.add_managed_policy(
            iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
        )
        # Create Lambda function for CreateOrder action
        create_order_lambda = _lambda.Function(
            self, "CreateOrderLambda",
            function_name=f"{app_name}-createorder-actions",
            role= create_order_lambda_role,
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="index.handler",
            code=_lambda.Code.from_asset(lambda_code_path),
            environment={
                "API_URL_PARAM": config.apigateway_url_param
            },
            # Enable Lambda Extension Layer for reading SSM Parameter and Secrets from local cache
            # Update ARN based on region & architecture here: https://docs.aws.amazon.com/systems-manager/latest/userguide/ps-integration-lambda-extensions.html
            layers=[_lambda.LayerVersion.from_layer_version_arn(
                self, "ParamterStoreLambdaExtensionLayer",
                layer_version_arn="arn:aws:lambda:us-west-2:345057560386:layer:AWS-Parameters-and-Secrets-Lambda-Extension:11"
            )],
            timeout=Duration.seconds(30),
            memory_size=256
        )

        # Create IAM role for Bedrock Agent
        agent_role = iam.Role(
            self, "BedrockShoppingAgentRole",
            role_name= f"{config.bedrock_shopping_agent_name}-{random_hash}-role",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for Bedrock Shopping Agent"
        )

        # Allow permission to invoke bedrock model. Make sure you have access granted to ue this foundation model.
        agent_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            resources=[f"arn:aws:bedrock:{self.region}::foundation-model/anthropic.claude-3-sonnet-20240229-v1:0"]
        ))

        # Allow permission to retrieve documents from Knowledge Base.
        agent_role.add_to_policy(iam.PolicyStatement(
            actions=[
                 "bedrock:Retrieve"
            ],
            resources=[f"arn:aws:bedrock:{self.region}:{self.account}:knowledge-base/{product_kb_id}"]
        ))

        # agent_role.add_to_policy(iam.PolicyStatement(
        #     effect=iam.Effect.ALLOW,
        #     actions=["logs:CreateLogStream", "logs:PutLogEvents"],
        #     resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:/aws/bedrock/agents/*"]
        # ))

        # Create Bedrock Agent
        agent = bedrock.CfnAgent(
            self, "ShoppingAgent",
            agent_name=f"{config.bedrock_shopping_agent_name}",
            agent_resource_role_arn=agent_role.role_arn,
            description="Shopping assistant agent using Bedrock",
            foundation_model="anthropic.claude-3-sonnet-20240229-v1:0",
            tags=config.bedrock_agent_tags,
            instruction=agent_instruction,
            auto_prepare=True,
            knowledge_bases=[
                bedrock.CfnAgent.AgentKnowledgeBaseProperty(
                    description="This knowledge base contains list of products, their attributes and descriptions from the product catalog.",
                    knowledge_base_id=product_kb_id,
                )
            ],
            prompt_override_configuration=bedrock.CfnAgent.PromptOverrideConfigurationProperty(
                prompt_configurations=[
                    bedrock.CfnAgent.PromptConfigurationProperty(
                        base_prompt_template=orchestration_prompt,
                        prompt_type="ORCHESTRATION",
                        prompt_state="ENABLED",
                        prompt_creation_mode="OVERRIDDEN",
                        inference_configuration=bedrock.CfnAgent.InferenceConfigurationProperty(
                            maximum_length=2048,
                            stop_sequences=["</error>", "</answer>", "</invoke>"],
                            temperature=0,
                            top_k=250,
                            top_p=1
                        )
                    ),
                    bedrock.CfnAgent.PromptConfigurationProperty(
                        base_prompt_template=kb_prompt,
                        prompt_type="KNOWLEDGE_BASE_RESPONSE_GENERATION",
                        prompt_state="DISABLED", # Disable the template to get raw search results from Knowledge Base
                        prompt_creation_mode="OVERRIDDEN",
                        inference_configuration=bedrock.CfnAgent.InferenceConfigurationProperty(
                            maximum_length=2048,
                            stop_sequences=["⏎⏎Human:"],
                            temperature=0,
                            top_k=250,
                            top_p=1
                        )
                    )
                ]
            ),
            action_groups=[
                bedrock.CfnAgent.AgentActionGroupProperty(
                    action_group_name="CreateOrder-actions",
                    description="Action group for creating orders",
                    action_group_executor=bedrock.CfnAgent.ActionGroupExecutorProperty(
                        lambda_=create_order_lambda.function_arn
                    ),
                    api_schema=bedrock.CfnAgent.APISchemaProperty(
                        payload=create_order_schema
                    )
                ),
                # Allow the agent to request the user for additional information when trying to complete a task
                bedrock.CfnAgent.AgentActionGroupProperty(
                    action_group_name="UserInputAction",
                    action_group_state="ENABLED",
                    parent_action_group_signature='AMAZON.UserInput'
                )
            ]
        )

        # Create Agent Alias
        alias = bedrock.CfnAgentAlias(
            self, "ShoppingAgentPRODAlias",
            agent_id=agent.attr_agent_id,
            agent_alias_name=f"PROD",
            description="Alias for production agent invocation",
            tags=config.bedrock_agent_tags
        )

        # Add resource-based policy to allow Bedrock to invoke the Lambda function
        create_order_lambda.add_permission(
            "AllowBedrockInvoke",
            principal=iam.ServicePrincipal("bedrock.amazonaws.com"),
            action="lambda:InvokeFunction",
            source_arn=f"arn:aws:bedrock:{self.region}:{self.account}:agent/{agent.attr_agent_id}"
        )

        # Store agent ID and alias ID in SSM Parameter Store
        ssm.StringParameter(
            self, "ShoppingAgentIdParameter",
            parameter_name=config.shopping_agent_id_param,
            string_value=agent.attr_agent_id
        )

        ssm.StringParameter(
            self, "ShoppingAgentAliasIdParameter",
            parameter_name=config.shopping_agent_alias_id_param,
            string_value=alias.attr_agent_alias_id
        )

        # Outputs
        CfnOutput(self, f"{config.bedrock_shopping_agent_name}-AgentId", value=agent.attr_agent_id, description="Bedrock Agent ID")
        CfnOutput(self, f"{config.bedrock_shopping_agent_name}-AgentAliasId", value=alias.attr_agent_alias_id, description="Bedrock Agent Alias ID")
        CfnOutput(self, f"{config.bedrock_shopping_agent_name}-AgentRoleArn", value=agent_role.role_arn, description="Bedrock Agent Role ARN")
        CfnOutput(self, "CreateOrderLambdaArn", value=create_order_lambda.function_arn, description="Create Order Lambda ARN")
        # CfnOutput(self, "ModelInvocationBucketName", value=model_invocation_bucket.bucket_name, description="Model Invocation Bucket Name")
        # CfnOutput(self, "ModelLogGroupName", value=model_log_group.log_group_name, description="Model Log Group Name")

