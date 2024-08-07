import hashlib
from aws_cdk import (
    NestedStack,
    aws_logs as logs,
    aws_iam as iam,
    custom_resources as cr,
    aws_logs as logs,
    aws_s3 as s3,
    CfnOutput,
    RemovalPolicy
)
from constructs import Construct
from lib.config import Config

class BedrockLoggingStack(NestedStack):

    def __init__(self, scope: Construct, construct_id: str, config: Config, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)


        # Create a CloudWatch log group for model invocation logs
        model_log_group = logs.LogGroup(self, "ModelLogGroup",
            log_group_name=f"/aws/bedrock/{self.account}-{self.region}-modelinvocations",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )

        # Create an S3 bucket for model invocation logs
        self.bedrock_logs_bucket = s3.Bucket(self, "BedrockLogsBucket",
            bucket_name=f"amazon-bedrock-logs-{self.account}-{self.region}".lower(),
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True
        )


        # Add bucket policy for Bedrock
        self.bedrock_logs_bucket.add_to_resource_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            principals=[iam.ServicePrincipal("bedrock.amazonaws.com")],
            actions=["s3:PutObject"],
            resources=[f"{self.bedrock_logs_bucket.bucket_arn}/AWSLogs/{self.account}/BedrockModelInvocationLogs/*"],
            conditions={
                "StringEquals": {"aws:SourceAccount": self.account},
                "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{self.region}:{self.account}:*"}
            }
        ))

        # Create the IAM role for Bedrock model invocation logging
        model_logging_role = iam.Role(self, "ModelLoggingRole",
            role_name=f"bedrock-model-logging-role-{self.region}-{self.account}",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            description="IAM role for Bedrock model invocation logging",
            inline_policies={
                'ModelLoggingPolicy': iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["logs:CreateLogStream", "logs:PutLogEvents"],
                            resources=[f"arn:aws:logs:{self.region}:{self.account}:log-group:{model_log_group.log_group_name}:log-stream:aws/bedrock/modelinvocations"]
                        ),
                        iam.PolicyStatement(
                            effect=iam.Effect.ALLOW,
                            actions=["s3:PutObject"],
                            resources=[f"{self.bedrock_logs_bucket.bucket_arn}/AWSLogs/{self.account}/BedrockModelInvocationLogs/*"]
                        )
                    ]
                )
            }
        )

        # Add trust relationship
        model_logging_role.assume_role_policy.add_statements(
            iam.PolicyStatement(
                effect=iam.Effect.ALLOW,
                principals=[iam.ServicePrincipal("bedrock.amazonaws.com")],
                actions=["sts:AssumeRole"],
                conditions={
                    "StringEquals": {"aws:SourceAccount": self.account},
                    "ArnLike": {"aws:SourceArn": f"arn:aws:bedrock:{self.region}:{self.account}:*"}
                }
            )
        )

        # Define the request body for the API call that the custom resource will use
        model_logging_params = {
            "loggingConfig": { 
                "cloudWatchConfig": { 
                    "largeDataDeliveryS3Config": { 
                    "bucketName": self.bedrock_logs_bucket.bucket_name,
                    "keyPrefix": ""
                    },
                    "logGroupName": model_log_group.log_group_name,
                    "roleArn": model_logging_role.role_arn
                },
                "embeddingDataDeliveryEnabled": True,
                "imageDataDeliveryEnabled": True,
                "textDataDeliveryEnabled": True
            }
        }

        # Define a custom resource to make an AWS SDK call to the Bedrock API
        model_logging_cr = cr.AwsCustomResource(self, "ModelLoggingCustomResource",
            on_create=cr.AwsSdkCall(
                service="Bedrock",
                action="putModelInvocationLoggingConfiguration",
                parameters=model_logging_params,
                physical_resource_id=cr.PhysicalResourceId.of("BedrockModelInvocationLogging")
            ),
            on_update=cr.AwsSdkCall(
                service="Bedrock",
                action="putModelInvocationLoggingConfiguration",
                parameters=model_logging_params,
                physical_resource_id=cr.PhysicalResourceId.of("BedrockModelInvocationLogging")
            ),
            policy=cr.AwsCustomResourcePolicy.from_sdk_calls(
                resources=cr.AwsCustomResourcePolicy.ANY_RESOURCE
            )
        )

        # Define IAM permission policy for the custom resource    
        model_logging_cr.grant_principal.add_to_principal_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=["bedrock:PutModelInvocationLoggingConfiguration", "iam:CreateServiceLinkedRole", "iam:PassRole"],
            resources=["*"],
        ))

        # Output the resources created
        CfnOutput(self, "ModelLogGroupName", value=model_log_group.log_group_name)
        CfnOutput(self, "ModelInvocationBucketName", value=self.bedrock_logs_bucket.bucket_name)
        CfnOutput(self, "ModelLoggingRoleArn", value=model_logging_role.role_arn)
