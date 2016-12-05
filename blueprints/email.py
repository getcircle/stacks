import os

import awacs.s3
from awacs.aws import (
    Allow,
    Condition,
    Policy,
    Principal,
    Statement,
    StringEquals,
)
from stacker.blueprints.base import Blueprint
from troposphere import (
    s3,
    Ref,
)

BUCKET = 'S3Bucket'
POLICY = 'S3BucketPolicy'


class EmailIngestion(Blueprint):

    LOCAL_PARAMETERS = {
        'BucketName': {
            'type': str,
            'description': 'The name to use for bucket',
        },
        'AWSAccountId': {
            'type': str,
            'description': 'The account id of the AWS account we\'re receiving emails in',
        },
    }

    PARAMETERS = {
        'LogBucketName': {
            'type': 'String',
            'description': 'The name of the bucket to log to',
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
                Action=[awacs.s3.PutObject, awacs.s3.PutObjectAcl],
                Resource=[awacs.s3.ARN(os.path.join(bucket_name, '*'))],
                Condition=Condition(
                    StringEquals('aws:Referer', self.local_parameters['AWSAccountId']),
                ),
                Principal=Principal('Service', 'ses.amazonaws.com'),
            )
        ]

        self.template.add_resource(
            s3.BucketPolicy(
                POLICY,
                Bucket=Ref(BUCKET),
                PolicyDocument=Policy(Statement=statements),
            ),
        )
