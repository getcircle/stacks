from awacs import s3
from awacs.aws import (
    Action,
    Allow,
    Policy,
    Statement,
)
policytypes = (dict, Policy)
from stacker.blueprints.base import Blueprint
from troposphere import (
    ecs,
    ec2,
    AWSObject,
    GetAtt,
    Join,
    Output,
    Ref,
)
from troposphere import elasticloadbalancing as elb
from troposphere.route53 import RecordSetType

ECS_SERVICE = 'ECSService'
ELB_SECURITY_GROUP = 'ELBSecurityGroup'
LOAD_BALANCER = 'LoadBalancer'
DNS_RECORD = 'DNSRecord'
PORT = 8200
TASK_DEFINITION = 'TaskDefinition'
S3_POLICY = 'S3Policy'


class IAMPolicy(AWSObject):
    resource_type = "AWS::IAM::Policy"

    props = {
        'Groups': ([basestring, Ref], False),
        'PolicyDocument': (policytypes, True),
        'PolicyName': (basestring, True),
        'Roles': ([basestring, Ref], False),
        'Users': ([basestring, Ref], False),
    }


class VaultService(Blueprint):

    PARAMETERS = {
        'BaseDomain': {
            'type': 'String',
            'description': 'Base domain for the stack.',
        },
        'DesiredCount': {
            'type': 'Number',
            'description': 'The number of simultaneous tasks you want to run',
            'default': '1',
        },
        'ECSCluster': {
            'type': 'String',
            'description': 'The ECS Cluster to launch the service in',
        },
        'ECSClusterIAMRole': {
            'type': 'String',
            'description': 'The IAM Role attached to the container instances',
        },
        'ECSClusterSecurityGroup': {
            'type': 'AWS::EC2::SecurityGroup::Id',
            'description': 'The security group for the ECS cluster',
        },
        'ELBCertName': {
            'type': 'String',
            'description': 'The SSL certificate name to use on the ELB.',
        },
        'PublicSubnets': {
            'type': 'List<AWS::EC2::Subnet::Id>',
            'description': 'Subnets to deploy public (elb) instances in.',
        },
        'TrustedNetwork': {
            'type': 'String',
            'description': 'CIDR block allowed to connect to empire ELB.',
        },
        'VpcId': {'type': 'AWS::EC2::VPC::Id', 'description': 'Vpc Id'},
    }

    def create_service(self):
        container_definition = ecs.ContainerDefinition(
            Name='vault',
            Image='lunohq/vault',
            Cpu=512,
            Memory=256,
            PortMappings=[ecs.PortMapping(
                ContainerPort=PORT,
                HostPort=PORT,
            )],
            Essential=True,
        )

        self.template.add_resource(
            ecs.TaskDefinition(
                TASK_DEFINITION,
                ContainerDefinitions=[container_definition],
                Volumes=[],
            )
        )

        self.template.add_resource(
            ecs.Service(
                ECS_SERVICE,
                Cluster=Ref('ECSCluster'),
                DesiredCount=Ref('DesiredCount'),
                LoadBalancers=[
                    ecs.LoadBalancer(
                        ContainerName='vault',
                        ContainerPort=PORT,
                        LoadBalancerName=Ref(LOAD_BALANCER),
                    ),
                ],
                TaskDefinition=Ref(TASK_DEFINITION),
                Role='ecsServiceRole',
            ),
        )

    def create_security_groups(self):
        # create SG for the ELB
        self.template.add_resource(
            ec2.SecurityGroup(
                ELB_SECURITY_GROUP,
                GroupDescription=ELB_SECURITY_GROUP,
                VpcId=Ref('VpcId'),
            ),
        )

        # allow SSL traffic to the ELB
        self.template.add_resource(
            ec2.SecurityGroupIngress(
                'VaultELBPort443FromTrusted',
                IpProtocol='tcp',
                FromPort='443',
                ToPort='443',
                CidrIp=Ref('TrustedNetwork'),
                GroupId=Ref(ELB_SECURITY_GROUP),
            ),
        )

        # allow the ELB to talk to the container instance on port 8200
        self.template.add_resource(
            ec2.SecurityGroupIngress(
                'ELBPort8200ToContainerPort8200',
                IpProtocol='tcp',
                FromPort=PORT,
                ToPort=PORT,
                SourceSecurityGroupId=Ref(ELB_SECURITY_GROUP),
                GroupId=Ref('ECSClusterSecurityGroup'),
            ),
        )

    def setup_listeners(self):
        cert_id = Join(
            '',
            [
                'arn:aws:iam::',
                Ref('AWS::AccountId'),
                ':server-certificate/',
                Ref('ELBCertName'),
            ],
        )
        listeners = [
            elb.Listener(
                LoadBalancerPort=443,
                InstancePort=PORT,
                Protocol='SSL',
                InstanceProtocol='TCP',
                SSLCertificateId=cert_id,
            ),
        ]
        return listeners

    def create_load_balancer(self):
        self.template.add_resource(
            elb.LoadBalancer(
                LOAD_BALANCER,
                Listeners=self.setup_listeners(),
                SecurityGroups=[Ref(ELB_SECURITY_GROUP)],
                Subnets=Ref('PublicSubnets'),
            ),
        )

        # Setup ELB DNS
        self.template.add_resource(
            RecordSetType(
                DNS_RECORD,
                HostedZoneName=Join('', [Ref('BaseDomain'), '.']),
                Comment='Valut ELB DNS',
                Name=Join('.', ['vault', Ref('BaseDomain')]),
                Type='CNAME',
                TTL='120',
                ResourceRecords=[
                    GetAtt(LOAD_BALANCER, 'DNSName'),
                ],
            ),
        )
        self.template.add_output(
            Output('ValutAPIUrl', Value=Ref(DNS_RECORD)),
        )

    def attach_s3_policy(self):
        policy = Policy(
            Statement=[
                Statement(
                    Effect=Allow,
                    Resource=[
                        s3.ARN('luno-blackbox'),
                        s3.ARN('luno-blackbox/*'),
                    ],
                    Action=[Action('s3', '*')],
                ),
            ],
        )
        self.template.add_resource(
            IAMPolicy(
                S3_POLICY,
                PolicyName='VaultAccess',
                PolicyDocument=policy,
                Roles=[Ref('ECSClusterIAMRole')],
            )
        )

    def create_template(self):
        self.create_security_groups()
        self.create_load_balancer()
        self.create_service()
        self.attach_s3_policy()
