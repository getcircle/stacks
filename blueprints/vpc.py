from stacker.blueprints.vpc import (
    DEFAULT_SG,
    VPC as StackerVPC,
    NAT_SG,
)
from troposphere import (
    ec2,
    Ref,
)


class VPC(StackerVPC):

    def create_nat_security_groups(self):
        output = super(VPC, self).create_nat_security_groups()
        # Allow SSH access to the NAT instances. To conserve resources the NAT
        # instances act as our bastion hosts for the time being
        nat_public_ssh = ec2.SecurityGroupIngress(
            'NatPublicSSHRule',
            IpProtocol='TCP',
            FromPort='22',
            ToPort='22',
            CidrIp='0.0.0.0/0',
            GroupId=Ref(NAT_SG),
        )
        self.template.add_resource(nat_public_ssh)

        # Since the NAT instances double as our bastion hosts, they should be
        # able to connect to all instances within the VPC
        nat_to_internal_ssh = ec2.SecurityGroupIngress(
            'NatToInternalSSHRule',
            IpProtocol='TCP',
            FromPort='22',
            ToPort='22',
            SourceSecurityGroupId=Ref(NAT_SG),
            GroupId=Ref(DEFAULT_SG),
        )
        self.template.add_resource(nat_to_internal_ssh)
        return output
