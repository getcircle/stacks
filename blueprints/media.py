import os

import awacs.s3
from awacs.aws import (
    Allow,
    AWSPrincipal,
    Everybody,
    Policy,
    Statement,
)
from stacker.blueprints.base import Blueprint
from troposphere import (
    s3,
    Ref,
)

BUCKET = 'S3Bucket'
POLICY = 'S3BucketPolicy'


class Bucket(Blueprint):

    LOCAL_PARAMETERS = {
        'BucketName': {
            'type': str,
            'description': 'The name to use for bucket',
        },
        'PublicPaths': {
            'type': str,
            'description': 'Specific set of paths to open up for the bucket',
            'default': '*',
        },
    }

    PARAMETERS = {
        'CorsAllowedOrigins': {
            'type': 'CommaDelimitedList',
            'description': 'Hostnames to enable CORS for',
        },
        'CorsAllowedMethods': {
            'type': 'CommaDelimitedList',
            'description': 'Allowed methods for CORS enabled origins',
            'default': 'GET',
        },
        'CorsMaxAge': {
            'type': 'Number',
            'description': 'Max age for the CORS rule',
            'default': '3000',
        },
        'CorsAllowedHeaders': {
            'type': 'CommaDelimitedList',
            'description': 'Allowed headers for CORS enabled origins',
            'default': '*',
        },
        'LogBucketName': {
            'type': 'String',
            'description': 'The name of the bucket to log to',
        },
    }

    def create_template(self):
        bucket_name = self.local_parameters['BucketName']
        rules = [
            s3.CorsRules(
                AllowedOrigins=Ref('CorsAllowedOrigins'),
                AllowedMethods=Ref('CorsAllowedMethods'),
                AllowedHeaders=Ref('CorsAllowedHeaders'),
                MaxAge=Ref('CorsMaxAge'),
            )
        ]
        self.template.add_resource(
            s3.Bucket(
                BUCKET,
                BucketName=bucket_name,
                CorsConfiguration=s3.CorsConfiguration(
                    CorsRules=rules,
                ),
                LoggingConfiguration=s3.LoggingConfiguration(
                    DestinationBucketName=Ref('LogBucketName'),
                    LogFilePrefix='%s/' % (bucket_name,),
                ),
            ),
        )

        statements = []
        public_paths = [path.strip() for path in self.local_parameters['PublicPaths'].split(',')]

        for public_path in public_paths:
            statements.append(
                Statement(
                    Effect=Allow,
                    Action=[awacs.s3.GetObject],
                    Resource=[awacs.s3.ARN(os.path.join(bucket_name, public_path))],
                    Principal=AWSPrincipal(Everybody),
                )
            )

        self.template.add_resource(
            s3.BucketPolicy(
                POLICY,
                Bucket=Ref(BUCKET),
                PolicyDocument=Policy(
                    Statement=statements,
                ),
            ),
        )
