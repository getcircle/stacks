from stacker.blueprints.base import Blueprint
from troposphere import (
    Base64,
    Ref,
    FindInMap,
    Join,
    Output,
    GetAtt,
    Not,
    Equals,
    If,
    Tags,
)
from troposphere import ec2, autoscaling, ecs
from troposphere.autoscaling import Tag as ASTag
from troposphere.cloudformation import WaitConditionHandle
from troposphere.iam import InstanceProfile, Policy, Role
from troposphere import elasticloadbalancing as elb
from troposphere.route53 import RecordSetType

from awacs.helpers.trust import (
    get_default_assumerole_policy,
    get_ecs_assumerole_policy,
)

from .policies import (
    ecs_agent_policy,
    empire_policy,
    logstream_policy,
    service_role_policy,
)

CLUSTER_SECURITY_GROUP = "SecurityGroup"
ELB_SECURITY_GROUP = "ELBSecurityGroup"
ECS_CLUSTER = "EmpireECSCluster"
EMPIRE_CONTROLLER_SERVICE = "EmpireControllerService"
EMPIRE_CONTROLLER_LOAD_BALANCER = "EmpireControllerLoadBalancer"
EMPIRE_CONTROLLER_ELB_DNS_RECORD = "EmpireControllerElbDnsRecord"
EMPIRE_CONTROLLER_CONTAINER_NAME = "empire"
EMPIRE_CONTROLLER_ROLE = "EmpireControllerRole"
EMPIRE_SERVICE_ROLE = "EmpireServiceRole"
EMPIRE_CONTROLLER_TASK_DEFINITION = "EmpireControllerTaskDefinition"


class Empire(Blueprint):
    PARAMETERS = {
        'VpcId': {'type': 'AWS::EC2::VPC::Id', 'description': 'Vpc Id'},
        'DefaultSG': {
            'type': 'AWS::EC2::SecurityGroup::Id',
            'description': 'Top level security group.',
        },
        'BaseDomain': {
            'type': 'String',
            'description': 'Base domain for the stack.',
        },
        'PrivateSubnets': {
            'type': 'List<AWS::EC2::Subnet::Id>',
            'description': 'Subnets to deploy private instances in.',
        },
        'PublicSubnets': {
            'type': 'List<AWS::EC2::Subnet::Id>',
            'description': 'Subnets to deploy public (elb) instances in.',
        },
        'InternalZone': {
            'type': 'String',
            'description': 'Internal Hosted Zone created by VPC',
        },
        'AvailabilityZones': {
            'type': 'CommaDelimitedList',
            'description': 'Availability Zones to deploy instances in.',
        },
        'InstanceType': {
            'type': 'String',
            'description': 'Empire AWS Instance Type',
            'default': 'm3.medium',
        },
        'DesiredInstances': {
            'type': 'Number',
            'description': 'Desired # of empire instances we want running.',
            'default': '3',
        },
        'MinInstances': {
            'type': 'Number',
            'description': 'Minimum # of empire instances.',
            'default': '3',
        },
        'MaxInstances': {
            'type': 'Number',
            'description': 'Maximum # of empire instances.',
            'default': '10',
        },
        'SshKeyName': {'type': 'AWS::EC2::KeyPair::KeyName'},
        'TrustedNetwork': {
            'type': 'String',
            'description': 'CIDR block allowed to connect to empire ELB.',
        },
        'ImageName': {
            'type': 'String',
            'description': (
                'The image name to use from the AMIMap (usually found in the config file.)'
            ),
            'default': 'empire',
        },
        'DatabaseSecurityGroup': {
            'type': 'AWS::EC2::SecurityGroup::Id',
            'description': 'Database security group.',
        },
        'ELBCertName': {
            'type': 'String',
            'description': (
                'The SSL certificate name to use on the ELB. Note: If this is set, non-HTTPS'
                ' access is disabled.'
            ),
            'default': '',
        },
        'EmpireGithubClientId': {
            'type': 'String',
            'description': (
                'Github Client Id to enable Github Authentication in Empire.'
            ),
        },
        'EmpireGithubClientSecret': {
            'type': 'String',
            'description': (
                'Github Client Secret to enable Github Authentication in Empire.'
            ),
        },
        'EmpireGithubOrganization': {
            'type': 'String',
            'description': (
                'Github Organization to enable Github Authentication in Empire.'
            ),
        },
        'EmpireDatabaseUser': {
            'type': 'String',
            'description': 'Empire DB user',
            'default': 'postgres',
        },
        'EmpireDatabaseHost': {
            'type': 'String',
            'description': 'RDS db host',
        },
        'EmpireDatabasePassword': {
            'type': 'String',
            'description': 'DB password for empire instance',
        },
        'EmpireTokenSecret': {
            'type': 'String',
            'description': (
                'String used to sign access tokens for clients in Empire. Should be somewhere'
                ' between 32-64 characters long'
            ),
        },
        'EmpireHekaTcpOutputAddress': {
            'type': 'String',
            'description': 'The TcpOutput address for Heka',
        },
        'EmpireDataDogAPIKey': {
            'type': 'String',
            'description': 'The API key to use for data dog',
        },
        'EmpireDataDogTags': {
            'type': 'String',
            'description': 'A comma delimited list of strings to use as tags for the dd-agent',
            'default': '',
        },
        'DockerRegistry': {
            'type': 'String',
            'description': 'Docker registry',
            'default': 'https://index.docker.io/v1/',
        },
        'DockerRegistryUser': {'type': 'String'},
        'DockerRegistryPassword': {'type': 'String', 'NoEcho': 'true'},
        'DockerRegistryEmail': {'type': 'String'},
        'ECSClusterName': {
            'type': 'String',
            'description': 'The name of the ECS cluster that runs empire',
            'default': 'empire',
        },
    }

    def create_conditions(self):
        ssl_condition = Not(Equals(Ref("ELBCertName"), ""))
        self.template.add_condition("UseSSL", ssl_condition)

    def create_security_groups(self):
        t = self.template

        t.add_resource(
            ec2.SecurityGroup(
                CLUSTER_SECURITY_GROUP,
                GroupDescription=CLUSTER_SECURITY_GROUP,
                VpcId=Ref("VpcId"),
            ),
        )
        t.add_output(
            Output(CLUSTER_SECURITY_GROUP, Value=Ref(CLUSTER_SECURITY_GROUP)),
        )

        # Add rule for access to DB
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireControllerDBAccess",
                IpProtocol='TCP',
                FromPort=5432,
                ToPort=5432,
                SourceSecurityGroupId=Ref(CLUSTER_SECURITY_GROUP),
                GroupId=Ref('DatabaseSecurityGroup'),
            ),
        )

        # Allow all ports within cluster
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireMinionAllTCPAccess",
                IpProtocol='-1',
                FromPort='-1',
                ToPort='-1',
                SourceSecurityGroupId=Ref(CLUSTER_SECURITY_GROUP),
                GroupId=Ref(CLUSTER_SECURITY_GROUP),
            ),
        )

        t.add_resource(
            ec2.SecurityGroup(
                ELB_SECURITY_GROUP,
                GroupDescription=ELB_SECURITY_GROUP,
                VpcId=Ref("VpcId"),
            ),
        )

        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireControllerELBPort80FromTrusted",
                IpProtocol='tcp',
                FromPort='80',
                ToPort='80',
                CidrIp=Ref("TrustedNetwork"),
                GroupId=Ref(ELB_SECURITY_GROUP),
            ),
        )
        t.add_resource(
            ec2.SecurityGroupIngress(
                "EmpireControllerELBPort443FromTrusted",
                IpProtocol='tcp',
                FromPort='443',
                ToPort='443',
                CidrIp=Ref("TrustedNetwork"),
                GroupId=Ref(ELB_SECURITY_GROUP),
            ),
        )

        # Empire controller runs on port 8080 on the container instance
        t.add_resource(
            ec2.SecurityGroupIngress(
                "ELBPort80ToControllerPort8080",
                IpProtocol='tcp',
                FromPort='8080',
                ToPort='8080',
                SourceSecurityGroupId=Ref(ELB_SECURITY_GROUP),
                GroupId=Ref(CLUSTER_SECURITY_GROUP),
            ),
        )

        # Application ELB Security Groups Internal
        for elb_name in ('public', 'private'):
            group_name = "Empire%sAppELBSG" % (elb_name.capitalize(),)
            t.add_resource(
                ec2.SecurityGroup(
                    group_name,
                    GroupDescription=group_name,
                    VpcId=Ref("VpcId"),
                    Tags=Tags(Name='%s-app-elb-sg' % (elb_name,)),
                ),
            )

            # Allow ELB to talk to cluster on 9000-10000
            t.add_resource(
                ec2.SecurityGroupIngress(
                    "Empire%sAppPort9000To10000" % (elb_name.capitalize(),),
                    IpProtocol="tcp",
                    FromPort=9000,
                    ToPort=10000,
                    SourceSecurityGroupId=Ref(group_name),
                    GroupId=Ref(CLUSTER_SECURITY_GROUP),
                ),
            )

            # Allow anything to talk to the ELB. If internal only internal
            # hosts will be able to talk to the elb.
            t.add_resource(
                ec2.SecurityGroupIngress(
                    "Empire%sELBAllow80" % (elb_name.capitalize(),),
                    IpProtocol="tcp",
                    FromPort=80,
                    ToPort=80,
                    CidrIp="0.0.0.0/0",
                    GroupId=Ref(group_name),
                ),
            )
            t.add_resource(
                ec2.SecurityGroupIngress(
                    "Empire%sELBAllow443" % (elb_name.capitalize(),),
                    IpProtocol="tcp",
                    FromPort=443,
                    ToPort=443,
                    CidrIp="0.0.0.0/0",
                    GroupId=Ref(group_name),
                ),
            )

    def setup_listeners(self):
        no_ssl = [
            elb.Listener(
                LoadBalancerPort=80,
                Protocol='TCP',
                InstancePort=8080,
                InstanceProtocol='TCP'
            ),
        ]

        cert_id = Join(
            "",
            [
                "arn:aws:iam::",
                Ref("AWS::AccountId"),
                ":server-certificate/",
                Ref("ELBCertName"),
            ],
        )
        with_ssl = []
        with_ssl.append(
            elb.Listener(
                LoadBalancerPort=443,
                InstancePort=8080,
                Protocol='SSL',
                InstanceProtocol="TCP",
                SSLCertificateId=cert_id,
            )
        )
        listeners = If("UseSSL", with_ssl, no_ssl)
        return listeners

    def create_load_balancer(self):
        t = self.template
        t.add_resource(
            elb.LoadBalancer(
                EMPIRE_CONTROLLER_LOAD_BALANCER,
                HealthCheck=elb.HealthCheck(
                    Target='HTTP:8080/health',
                    HealthyThreshold=3,
                    UnhealthyThreshold=3,
                    Interval=5,
                    Timeout=3,
                ),
                Listeners=self.setup_listeners(),
                SecurityGroups=[Ref(ELB_SECURITY_GROUP)],
                Subnets=Ref("PublicSubnets"),
            ),
        )

        # Setup ELB DNS
        t.add_resource(
            RecordSetType(
                EMPIRE_CONTROLLER_ELB_DNS_RECORD,
                HostedZoneName=Join("", [Ref("BaseDomain"), "."]),
                Comment='Router ELB DNS',
                Name=Join('.', ["empire", Ref("BaseDomain")]),
                Type='CNAME',
                TTL='120',
                ResourceRecords=[
                    GetAtt(EMPIRE_CONTROLLER_LOAD_BALANCER, 'DNSName'),
                ],
            ),
        )
        t.add_output(
            Output(
                'EmpireAPIUrl',
                Value=Ref(EMPIRE_CONTROLLER_ELB_DNS_RECORD),
            ),
        )

    def build_block_device(self):
        docker_volume = autoscaling.BlockDeviceMapping(
            DeviceName="/dev/sdh",
            Ebs=autoscaling.EBSBlockDevice(
                DeleteOnTermination=True,
                VolumeSize="50",
            ),
        )
        swap_volume = autoscaling.BlockDeviceMapping(
            DeviceName="/dev/sdi",
            Ebs=autoscaling.EBSBlockDevice(
                DeleteOnTermination=True,
                VolumeSize="16",
            ),
        )
        return [docker_volume, swap_volume]

    def generate_user_data(self):
        contents = Join('', self.generate_seed_contents())
        stanza = Base64(Join(
            '',
            [
                '#cloud-config\n',
                'write_files:\n',
                '  - encoding: b64\n',
                '    content: ', Base64(contents), '\n',
                '    owner: root:root\n',
                '    path: /etc/empire/seed\n',
                '    permissions: 0640\n'
            ]
        ))
        return stanza

    def generate_seed_contents(self):
        seed = [
            'EMPIRE_HOSTGROUP=empire_combined\n',
            'EMPIRE_ECS_SERVICE_ROLE=', Ref(EMPIRE_SERVICE_ROLE), '\n',
            'EMPIRE_ELB_SG_PRIVATE=', Ref('EmpirePrivateAppELBSG'), '\n',
            'EMPIRE_ELB_SG_PUBLIC=', Ref('EmpirePublicAppELBSG'), '\n',
            'EMPIRE_EC2_SUBNETS_PRIVATE=',
            Join(',', Ref('PrivateSubnets')), '\n',
            'EMPIRE_EC2_SUBNETS_PUBLIC=',
            Join(',', Ref('PublicSubnets')), '\n',
            'EMPIRE_DATABASE_USER=', Ref('EmpireDatabaseUser'), '\n',
            'EMPIRE_DATABASE_PASSWORD=', Ref('EmpireDatabasePassword'), '\n',
            'EMPIRE_DATABASE_HOST=', Ref('EmpireDatabaseHost'), '\n',
            'EMPIRE_ROUTE53_INTERNAL_ZONE_ID=', Ref('InternalZone'), '\n',
            'EMPIRE_HEKA_TCP_OUTPUT_ADDRESS=', Ref('EmpireHekaTcpOutputAddress'), '\n',
            'EMPIRE_DATA_DOG_API_KEY=', Ref('EmpireDataDogAPIKey'), '\n',
            'EMPIRE_DATA_DOG_TAGS=', Ref('EmpireDataDogTags'), '\n',
            'ECS_CLUSTER=', Ref(ECS_CLUSTER), '\n',
            'EMPIRE_GITHUB_CLIENT_ID=', Ref('EmpireGithubClientId'), '\n',
            'EMPIRE_GITHUB_CLIENT_SECRET=', Ref('EmpireGithubClientSecret'), '\n',
            'EMPIRE_GITHUB_ORGANIZATION=', Ref('EmpireGithubOrganization'), '\n',
            'ENABLE_STREAMING_LOGS=true', '\n',
            'EMPIRE_TOKEN_SECRET=', Ref('EmpireTokenSecret'), '\n',
            'DOCKER_REGISTRY=', Ref('DockerRegistry'), '\n',
            'DOCKER_USER=', Ref('DockerRegistryUser'), '\n',
            'DOCKER_PASS=', Ref('DockerRegistryPassword'), '\n',
            'DOCKER_EMAIL=', Ref('DockerRegistryEmail'), '\n',
        ]
        return seed

    def create_iam_profile(self):
        emp_policy = Policy(
            PolicyName="EmpireControllerPolicy",
            PolicyDocument=empire_policy(),
        )

        empire_controller_role = Role(
            EMPIRE_CONTROLLER_ROLE,
            AssumeRolePolicyDocument=get_default_assumerole_policy(),
            Path="/",
            Policies=[
                emp_policy,
                Policy(
                    PolicyName="%s-ecs-agent" % (self.context.namespace,),
                    PolicyDocument=ecs_agent_policy(),
                ),
                Policy(
                    PolicyName="%s-kinesis-logging" % (self.context.namespace,),
                    PolicyDocument=logstream_policy(),
                ),
            ],
        )
        self.template.add_resource(empire_controller_role)
        self.template.add_resource(
            InstanceProfile(
                "EmpireControllerProfile",
                Path="/",
                Roles=[Ref(EMPIRE_CONTROLLER_ROLE)],
            ),
        )
        self.template.add_output(
            Output(EMPIRE_CONTROLLER_ROLE, Value=Ref(EMPIRE_CONTROLLER_ROLE))
        )

        empire_service_role = Role(
            EMPIRE_SERVICE_ROLE,
            AssumeRolePolicyDocument=get_ecs_assumerole_policy(),
            Path="/",
            Policies=[
                Policy(
                    PolicyName="ecsServiceRolePolicy",
                    PolicyDocument=service_role_policy(),
                ),
            ],
        )
        self.template.add_resource(empire_service_role)

    def create_ecs_cluster(self):
        ecs_cluster = ecs.Cluster(ECS_CLUSTER)
        self.template.add_resource(ecs_cluster)

    def create_autoscaling_group(self):
        t = self.template
        t.add_resource(
            autoscaling.LaunchConfiguration(
                'EmpireControllerLaunchConfig',
                IamInstanceProfile=GetAtt("EmpireControllerProfile", "Arn"),
                ImageId=FindInMap('AmiMap', Ref("AWS::Region"), Ref("ImageName")),
                BlockDeviceMappings=self.build_block_device(),
                InstanceType=Ref("InstanceType"),
                KeyName=Ref("SshKeyName"),
                SecurityGroups=[Ref("DefaultSG"), Ref(CLUSTER_SECURITY_GROUP)],
                UserData=self.generate_user_data(),
            ),
        )
        t.add_resource(
            autoscaling.AutoScalingGroup(
                'EmpireControllerAutoscalingGroup',
                AvailabilityZones=Ref("AvailabilityZones"),
                LaunchConfigurationName=Ref("EmpireControllerLaunchConfig"),
                DesiredCapacity=Ref("DesiredInstances"),
                MinSize=Ref("MinInstances"),
                MaxSize=Ref("MaxInstances"),
                VPCZoneIdentifier=Ref("PrivateSubnets"),
                LoadBalancerNames=[Ref(EMPIRE_CONTROLLER_LOAD_BALANCER), ],
                Tags=[ASTag('Name', 'empire', True)],
            ),
        )

    def create_template(self):
        self.create_conditions()
        self.create_security_groups()
        self.create_ecs_cluster()
        self.create_load_balancer()
        self.create_iam_profile()
        self.create_autoscaling_group()
        self.template.add_resource(WaitConditionHandle("ForceUpdate"))
