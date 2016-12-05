from stacker.blueprints.base import Blueprint
from troposphere import Ref
from troposphere import ec2


class API(Blueprint):

    PARAMETERS = {
        'RDSSecurityGroup': {
            'type': 'AWS::EC2::SecurityGroup::Id',
            'description': 'Security group for the API database.',
        },
        'RedisSecurityGroup': {
            'type': 'AWS::EC2::SecurityGroup::Id',
            'description': 'Security group for the redis database.',
        },
        'MinionSecurityGroup': {
            'type': 'AWS::EC2::SecurityGroup::Id',
            'description': 'Security group for the minions running the API service.',
        },
    }

    def create_security_groups(self):
        # Add rules to access RDS and Redis databases from the empire minions
        # that will run the API
        self.template.add_resource(
            ec2.SecurityGroupIngress(
                'EmpireMinionDatabaseAccess',
                IpProtocol='TCP',
                FromPort=5432,
                ToPort=5432,
                SourceSecurityGroupId=Ref('MinionSecurityGroup'),
                GroupId=Ref('RDSSecurityGroup'),
            ),
        )
        self.template.add_resource(
            ec2.SecurityGroupIngress(
                'EmpireMinionRedisAccess',
                IpProtocol='TCP',
                FromPort=6379,
                ToPort=6379,
                SourceSecurityGroupId=Ref('MinionSecurityGroup'),
                GroupId=Ref('RedisSecurityGroup'),
            ),
        )

    def create_template(self):
        self.create_security_groups()
