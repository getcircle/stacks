import os

import awacs.s3
from awacs.aws import (
    Allow,
    Policy,
    Statement,
)
from stacker.blueprints.base import Blueprint
from troposphere import (
    Ref,
    iam,
    s3,
)

BUCKET = 'S3Bucket'
READ_POLICY = 'ReadPolicy'


class Bucket(Blueprint):

    LOCAL_PARAMETERS = {
        'BucketName': {
            'type': str,
            'description': 'The name to use for bucket',
        },
    }

    PARAMETERS = {
        'LogBucketName': {
            'type': 'String',
            'description': 'The name of the bucket to log to',
        },
        'ReadRoles': {
            'type': 'CommaDelimitedList',
            'description': (
                'The name of the IAM profile that should have access to the private bucket'
            ),
            'default': '',
        },
    }

    def create_template(self):
        bucket_name = self.local_parameters['BucketName']
        self.template.add_resource(
            s3.Bucket(
                BUCKET,
                BucketName=bucket_name,
                LoggingConfiguration=s3.LoggingConfiguration(
                    DestinationBucketName=Ref('LogBucketName'),
                    LogFilePrefix='%s/' % (bucket_name,),
                ),
            ),
        )
        statements = [
            Statement(
                Effect=Allow,
                Action=[awacs.s3.GetObject, awacs.s3.ListBucket],
                Resource=[awacs.s3.ARN(bucket_name), awacs.s3.ARN(os.path.join(bucket_name, '*'))],
            ),
        ]
        self.template.add_resource(
            iam.PolicyType(
                READ_POLICY,
                PolicyName='PrivateBucketReadPolicy',
                PolicyDocument=Policy(
                    Statement=statements,
                ),
                Roles=Ref('ReadRoles'),
            ),
        )
