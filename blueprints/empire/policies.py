import logging

from awacs.aws import (
    Allow,
    Action,
    Policy,
    Statement,
)

from awacs import (
    ec2,
    ecs,
    iam,
    kinesis,
    route53,
)
from awacs import elasticloadbalancing as elb

logger = logging.getLogger(__name__)


def ecs_agent_policy():
    policy = Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Resource=["*"],
                Action=[
                    ecs.CreateCluster,
                    ecs.RegisterContainerInstance,
                    ecs.DeregisterContainerInstance,
                    ecs.DiscoverPollEndpoint,
                    ecs.ECSAction("Submit*"),
                    ecs.Poll,
                ],
            ),
        ]
    )
    return policy


def empire_policy():
    policy = Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Resource=["*"],
                Action=[
                    ecs.CreateService,
                    ecs.DeleteService,
                    ecs.DeregisterTaskDefinition,
                    ecs.ECSAction("Describe*"),
                    ecs.ECSAction("List*"),
                    ecs.RegisterTaskDefinition,
                    ecs.RunTask,
                    ecs.StartTask,
                    ecs.StopTask,
                    ecs.SubmitTaskStateChange,
                    ecs.UpdateService,
                ],
            ),
            Statement(
                Effect=Allow,
                # TODO: Limit to specific ELB?
                Resource=["*"],
                Action=[
                    elb.DeleteLoadBalancer,
                    elb.CreateLoadBalancer,
                    elb.DescribeLoadBalancers,
                    elb.DescribeTags,
                    elb.ConfigureHealthCheck,
                    elb.ModifyLoadBalancerAttributes,
                ],
            ),
            Statement(
                Effect=Allow,
                Resource=["*"],
                Action=[ec2.DescribeSubnets, ec2.DescribeSecurityGroups],
            ),
            Statement(
                Effect=Allow,
                Action=[
                    iam.GetServerCertificate,
                    iam.UploadServerCertificate,
                    iam.DeleteServerCertificate,
                    iam.PassRole,
                ],
                Resource=["*"],
            ),
            Statement(
                Effect=Allow,
                Action=[
                    Action("route53", "ListHostedZonesByName"),
                    route53.ChangeResourceRecordSets,
                    route53.ListHostedZones,
                    route53.GetHostedZone,
                ],
                # TODO: Limit to specific zones
                Resource=["*"],
            ),
            Statement(
                Effect=Allow,
                Action=[
                    kinesis.DescribeStream,
                    Action(kinesis.prefix, "Get*"),
                    Action(kinesis.prefix, "List*")
                ],
                Resource=["*"],
            ),
        ]
    )
    return policy


def service_role_policy():
    policy = Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Resource=["*"],
                Action=[
                    ec2.AuthorizeSecurityGroupIngress,
                    ec2.Action("ec2", "Describe*"),
                    elb.DeregisterInstancesFromLoadBalancer,
                    elb.ELBAction("Describe*"),
                    elb.RegisterInstancesWithLoadBalancer,
                ],
            ),
        ],
    )
    return policy


def logstream_policy():
    """Policy needed for logspout -> kinesis log streaming."""
    p = Policy(
        Statement=[
            Statement(
                Effect=Allow,
                Resource=["*"],
                Action=[
                    kinesis.CreateStream, kinesis.DescribeStream,
                    Action(kinesis.prefix, "AddTagsToStream"),
                    Action(kinesis.prefix, "PutRecords")
                ])
        ]
    )
    return p
