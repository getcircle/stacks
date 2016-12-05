import awacs.route53
import awacs.s3
import awacs.sns
import awacs.ses
from awacs.aws import (
    Allow,
    Policy,
    Statement,
)
import boto3
from stacker.blueprints.base import Blueprint
from troposphere import (
    iam,
    Join,
    Output,
    Ref,
)

ROUTE_53_POLICY = 'Route53Policy'
SERVICES_USER = 'User'
S3_BUCKET_POLICY = 'S3BucketPolicy'
SNS_APPLICATIONS_POLICY = 'SNSApplicationsPolicy'
SES_POLICY = 'SESPolicy'


class ServicesUser(Blueprint):

    LOCAL_PARAMETERS = {
        'BaseDomain': {
            'type': str,
            'description': 'The domain of the hosted zone we\'ll create records in',
        },
        'S3Buckets': {
            'type': list,
            'description': 'A list of S3 buckets the user should have access to',
        },
        'SNSApplicationARNs': {
            'type': str,
            'description': (
                'A comma delimited string of SNS Applications the user can create endpoints for'
            ),
        },
    }

    PARAMETERS = {}

    def create_user(self):
        self.template.add_resource(
            iam.User(
                SERVICES_USER,
                Path='/',
            ),
        )
        self.template.add_output(Output(SERVICES_USER, Value=Ref(SERVICES_USER)))

    def create_s3_policy(self):
        statements = []
        for bucket in self.local_parameters['S3Buckets']:
            statements.append(
                Statement(
                    Effect=Allow,
                    Action=[
                        awacs.s3.GetBucketLocation,
                        awacs.s3.ListBucket,
                    ],
                    Resource=[awacs.s3.ARN(bucket)],
                )
            )
            statements.append(
                Statement(
                    Effect=Allow,
                    Action=[awacs.s3.GetObject, awacs.s3.PutObject, awacs.s3.DeleteObject],
                    Resource=[Join('/', [awacs.s3.ARN(bucket), '*'])],
                )
            )

        self.template.add_resource(
            iam.PolicyType(
                S3_BUCKET_POLICY,
                PolicyName=S3_BUCKET_POLICY,
                PolicyDocument=Policy(Statement=statements),
                Users=[Ref(SERVICES_USER)],
            ),
        )

    def create_sns_applications_policy(self):
        statements = [
            Statement(
                Effect=Allow,
                Action=[
                    awacs.sns.CreatePlatformEndpoint,
                    awacs.sns.Publish,
                    awacs.sns.DeleteEndpoint,
                ],
                Resource=self.local_parameters['SNSApplicationARNs'].split(','),
            ),
        ]
        self.template.add_resource(
            iam.PolicyType(
                SNS_APPLICATIONS_POLICY,
                PolicyName=SNS_APPLICATIONS_POLICY,
                PolicyDocument=Policy(Statement=statements),
                Users=[Ref(SERVICES_USER)],
            ),
        )

    def create_ses_policy(self):
        statements = [
            Statement(
                Effect=Allow,
                Action=[
                    awacs.ses.SendEmail,
                    awacs.ses.VerifyDomainIdentity,
                ],
                Resource=['*'],
            ),
        ]
        self.template.add_resource(
            iam.PolicyType(
                SES_POLICY,
                PolicyName=SES_POLICY,
                PolicyDocument=Policy(Statement=statements),
                Users=[Ref(SERVICES_USER)],
            ),
        )

    def create_route53_policy(self):
        client = boto3.client('route53')
        response = client.list_hosted_zones_by_name(
            DNSName=self.local_parameters['BaseDomain'],
            MaxItems='1',
        )
        try:
            # id comes back as /hostedzone/<id>, we want to strip the first "/"
            hosted_zone = response['HostedZones'][0]['Id'][1:]
        except (KeyError, IndexError):
            raise ValueError('Failed to fetch hosted zone: %s - %s' % (
                self.local_parameters['BaseDomain'],
                response,
            ))

        statements = [
            Statement(
                Effect=Allow,
                Action=[
                    awacs.route53.GetHostedZone,
                    awacs.route53.ChangeResourceRecordSets,
                ],
                Resource=[awacs.route53.ARN(hosted_zone)],
            ),
        ]
        self.template.add_resource(
            iam.PolicyType(
                ROUTE_53_POLICY,
                PolicyName=ROUTE_53_POLICY,
                PolicyDocument=Policy(Statement=statements),
                Users=[Ref(SERVICES_USER)],
            ),
        )

    def create_template(self):
        self.create_user()
        self.create_s3_policy()
        self.create_sns_applications_policy()
        self.create_ses_policy()
        self.create_route53_policy()
