import os
import hashlib
from aws_cdk import (
    NestedStack,
    aws_ec2 as ec2,
    aws_ecs as ecs,
    aws_ecs_patterns as ecs_patterns,
    aws_iam as iam,
    aws_logs as logs,
    aws_elasticloadbalancingv2 as elb,
    aws_elasticloadbalancingv2_actions as elb_actions,
    aws_ecr_assets as ecr_assets,
    aws_certificatemanager as acm,
    aws_route53 as route53,
    aws_route53_targets as targets,
    Duration,
    CfnOutput
)
from constructs import Construct

class EcsStack(NestedStack):
    def __init__(self, scope: Construct, construct_id: str, app_name: str, config, user_pool= None, user_pool_client=None, user_pool_domain= None, application_dns_name=None, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        self.application_dns_name = application_dns_name
        self.domain_name = config.domain_name if hasattr(config, 'domain_name') else None
        self.hosted_zone_id = config.hosted_zone_id if hasattr(config, 'hosted_zone_id') else None


        # Create VPC
        vpc = ec2.Vpc(self, f"{app_name}-vpc", max_azs=2)
        # Create ECS Cluster
        cluster = ecs.Cluster(self, f"{app_name}-cluster", vpc=vpc, cluster_name=f"{app_name}-{self.region}-cluster")

        # Create Task Role with least privilege
        task_role = iam.Role(
            self,
            f"{app_name}-task-role",
            assumed_by=iam.ServicePrincipal("ecs-tasks.amazonaws.com"),
        )

        task_role.add_to_policy(iam.PolicyStatement(
            actions=["ssm:GetParameter"],
            resources=[f"arn:aws:ssm:{self.region}:{self.account}:parameter/{app_name}/*"]
        ))

        # Create Task Definition
        task_definition = ecs.FargateTaskDefinition(
            self,
            f"{app_name}-task-def",
            cpu=512,
            memory_limit_mib=1024,
            task_role=task_role
        )

        # Define the Docker Image for our container
        path = os.path.join(os.path.dirname(__file__), "..", "..", "source", "retail_genai_assistant_app")
        docker_image = ecr_assets.DockerImageAsset(
            self,
             f"{app_name}-docker-image",
            directory=path
        )

        # Add container to Task Definition
        container = task_definition.add_container(
            f"{app_name}-container",
            image=ecs.ContainerImage.from_docker_image_asset(docker_image),
            logging=ecs.LogDrivers.aws_logs(
                stream_prefix=f"ecs/{app_name}-{self.region}",
                log_retention=logs.RetentionDays.TWO_WEEKS
            ),
            environment={
                "STREAMLIT_SERVER_PORT": "8501",
                "STREAMLIT_SERVER_ADDRESS": "0.0.0.0"
            }
        )

        container.add_port_mappings(ecs.PortMapping(container_port=8501))

        # Security Groups
        alb_security_group = ec2.SecurityGroup(
            self,
            "AlbSecurityGroup",
            vpc=vpc,
            description="Security group for the Application Load Balancer",
            security_group_name=f"{app_name}-alb-sg-{self.region}"
        )

        ecs_security_group = ec2.SecurityGroup(
            self,
            "EcsSecurityGroup",
            vpc=vpc,
            description="Security group for the ECS service"
        )

        # Create ALB
        load_balancer = elb.ApplicationLoadBalancer(
            self,
            f"{app_name}-alb",
            vpc=vpc,
            internet_facing=True,
            security_group=alb_security_group,
            load_balancer_name=f"retail-genai-{self.region}-alb"
        )

        # Allow traffic from ALB to ECS tasks
        ecs_security_group.add_ingress_rule(
            alb_security_group,
            ec2.Port.tcp(8501),
            "Allow inbound traffic from ALB to ECS tasks"
        )

        certificate = None
        if self.domain_name and self.hosted_zone_id:
            # Create ACM certificate
            hosted_zone = route53.HostedZone.from_hosted_zone_attributes(
                self, "HostedZone",
                hosted_zone_id=self.hosted_zone_id,
                zone_name=self.domain_name
            )

            # Create A record in Route 53
            route53.ARecord(
                self,
                "AliasRecord",
                zone=hosted_zone,
                target=route53.RecordTarget.from_alias(targets.LoadBalancerTarget(load_balancer)),
                record_name=self.application_dns_name
            )

            certificate = acm.Certificate(
                self, 
                f"{app_name}-certificate",
                certificate_name=f"{app_name}-certificate",
                domain_name=self.application_dns_name,
                validation=acm.CertificateValidation.from_dns(hosted_zone)
            )

            # Allow HTTPS inbound to ALB
            alb_security_group.add_ingress_rule(
                ec2.Peer.any_ipv4(),
                ec2.Port.tcp(443),
                "Allow HTTPS inbound"
            )

            # HTTP to HTTPS redirect
            load_balancer.add_redirect(
                source_port=80,
                target_port=443,
                source_protocol=elb.ApplicationProtocol.HTTP,
                target_protocol=elb.ApplicationProtocol.HTTPS
            )
        else:
            # Allow HTTP inbound to ALB
            alb_security_group.add_ingress_rule(
                ec2.Peer.any_ipv4(),
                ec2.Port.tcp(80),
                "Allow HTTP inbound"
            )

        # Create Fargate Service
        fargate_service = ecs_patterns.ApplicationLoadBalancedFargateService(
            self,
            f"{app_name}-service",
            cluster=cluster,
            task_definition=task_definition,
            desired_count=config.number_of_tasks,
            public_load_balancer=True,
            assign_public_ip=False,
            listener_port=443 if certificate else 80,
            protocol=elb.ApplicationProtocol.HTTPS if certificate else elb.ApplicationProtocol.HTTP,
            certificate=certificate,
            load_balancer=load_balancer,
            security_groups=[ecs_security_group],
            task_subnets=ec2.SubnetSelection(subnet_type=ec2.SubnetType.PRIVATE_WITH_EGRESS),
            service_name=f"{app_name}-{self.region}-service"
        )

        # Setup AutoScaling policy
        scaling = fargate_service.service.auto_scale_task_count(max_capacity=4)
        scaling.scale_on_cpu_utilization(
            "CpuScaling",
            target_utilization_percent=80,
            scale_in_cooldown=Duration.seconds(60),
            scale_out_cooldown=Duration.seconds(60),
        )

        # Configure health check
        fargate_service.target_group.configure_health_check(
            path="/healthz",
            healthy_http_codes="200",
            interval=Duration.seconds(60),
            timeout=Duration.seconds(5)
        )

        # Add Cognito authentication to ALB
        if user_pool and user_pool_client and user_pool_domain:
            fargate_service.listener.add_action(
                "AuthenticateAction",
                conditions=[elb.ListenerCondition.path_patterns(["/*"])],
                priority=1,
                action=elb_actions.AuthenticateCognitoAction(
                    next=elb.ListenerAction.forward([fargate_service.target_group]),
                    user_pool=user_pool,
                    user_pool_client=user_pool_client,
                    user_pool_domain=user_pool_domain
                )
            )

        CfnOutput(self, "RetailGenAIAssistantAppURL", value=fargate_service.load_balancer.load_balancer_dns_name)
