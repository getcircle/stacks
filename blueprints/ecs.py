from awacs.helpers.trust import get_default_assumerole_policy
from stacker.blueprints.asg import AutoscalingGroup
from troposphere import (
    ec2,
    ecs,
    Base64,
    GetAtt,
    Join,
    Output,
    Ref,
)
from troposphere.iam import InstanceProfile, Policy, Role

from .empire.policies import ecs_agent_policy

CLUSTER_SECURITY_GROUP = 'ECSSecurityGroup'
ECS_AGENT_ROLE = 'ECSAgentRole'
ECS_AGENT_PROFILE = 'ECSAgentProfile'


class DefaultEcs(AutoscalingGroup):

    LOCAL_PARAMETERS = {
        'ECSClusterName': {
            'type': str,
            'description': 'Name of the ECS cluster to create',
        },
    }

    def _get_parameters(self, *args, **kwargs):
        parameters = super(DefaultEcs, self)._get_parameters()
        parameters['DesiredCapacity'] = {
            'type': 'Number',
            'description': 'Deisred # of ecs instances we want running.',
            'default': '1',
        }
        parameters['DockerRegistry'] = {
            'type': 'String',
            'description': 'Docker registry',
            'default': 'https://index.docker.io/v1/',
        }
        parameters['DockerRegistryUser'] = {'type': 'String'}
        parameters['DockerRegistryPassword'] = {'type': 'String', 'NoEcho': 'true'}
        parameters['DockerRegistryEmail'] = {'type': 'String'}
        parameters['VpcId'] = {'type': 'AWS::EC2::VPC::Id', 'description': 'Vpc Id'}
        return parameters

    def generate_user_data(self):
        docker_auth_data = [
            '{', '"', Ref('DockerRegistry'), '"', ':',
            '{', '"email":', '"', Ref('DockerRegistryEmail'), '"', ',',
            '"auth":', '"',
            Base64(Join(':', [Ref('DockerRegistryUser'), Ref('DockerRegistryPassword')])),
            '"', '}', '}',
        ]
        docker_auth = Join('', docker_auth_data)
        user_data = [
            'ECS_CLUSTER=', Ref(self.local_parameters['ECSClusterName']), '\n',
            'ECS_ENGINE_AUTH_TYPE=dockercfg\n',
            'ECS_ENGINE_AUTH_DATA=', docker_auth, '\n',
        ]
        contents = Join('', user_data)
        stanza = Base64(Join(
            '',
            [
                '#cloud-config\n',
                'write_files:\n',
                '   - encoding: b64\n',
                '     content: ', Base64(contents), '\n',
                '     owner: root:root\n',
                '     path: /etc/ecs/ecs.config\n',
                '     permissions: 0640\n',
            ],
        ))
        return stanza

    def create_ecs_iam_profile(self):
        ecs_agent_role = Role(
            ECS_AGENT_ROLE,
            AssumeRolePolicyDocument=get_default_assumerole_policy(),
            Path='/',
            Policies=[
                Policy(
                    PolicyName='%s-ecs-agent' % (self.context.namespace,),
                    PolicyDocument=ecs_agent_policy(),
                ),
            ],
        )

        self.template.add_resource(ecs_agent_role)
        self.template.add_resource(
            InstanceProfile(
                ECS_AGENT_PROFILE,
                Path='/',
                Roles=[Ref(ECS_AGENT_ROLE)],
            ),
        )
        self.template.add_output(
            Output('IAMRole', Value=Ref(ECS_AGENT_ROLE)),
        )

    def create_ecs_security_group(self):
        self.template.add_resource(
            ec2.SecurityGroup(
                CLUSTER_SECURITY_GROUP,
                GroupDescription=CLUSTER_SECURITY_GROUP,
                VpcId=Ref('VpcId'),
            ),
        )
        self.template.add_output(
            Output('SecurityGroup', Value=Ref(CLUSTER_SECURITY_GROUP)),
        )

    def create_cluster(self):
        self.template.add_resource(
            ecs.Cluster(self.local_parameters['ECSClusterName']),
        )
        self.template.add_output(
            Output('Cluster', Value=Ref(self.local_parameters['ECSClusterName'])),
        )

    def get_launch_configuration_parameters(self):
        parameters = super(DefaultEcs, self).get_launch_configuration_parameters()
        parameters['UserData'] = self.generate_user_data()
        parameters['IamInstanceProfile'] = GetAtt(ECS_AGENT_PROFILE, 'Arn')
        return parameters

    def get_autoscaling_group_parameters(self):
        parameters = super(DefaultEcs, self).get_autoscaling_group_parameters()
        parameters['DesiredCapacity'] = Ref('DesiredCapacity')
        return parameters

    def get_launch_configuration_security_groups(self, *args, **kwargs):
        security_groups = super(
            DefaultEcs,
            self,
        ).get_launch_configuration_security_groups(*args, **kwargs)
        security_groups.append(Ref(CLUSTER_SECURITY_GROUP))
        return security_groups

    def create_template(self, *args, **kwargs):
        super(DefaultEcs, self).create_template(*args, **kwargs)
        self.create_ecs_security_group()
        self.create_cluster()
        self.create_ecs_iam_profile()
