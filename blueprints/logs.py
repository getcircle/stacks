from stacker.blueprints.base import Blueprint
from troposphere import (
    s3,
    Output,
    Ref,
)

BUCKET = 'S3Bucket'


class Bucket(Blueprint):

    LOCAL_PARAMETERS = {
        'BucketName': {
            'type': str,
            'description': 'The name to use for bucket',
        },
    }

    def create_template(self):
        bucket_name = self.local_parameters['BucketName']
        self.template.add_resource(
            s3.Bucket(
                BUCKET,
                AccessControl='LogDeliveryWrite',
                BucketName=bucket_name,
            ),
        )
        self.template.add_output(
            Output(BUCKET, Value=Ref(BUCKET)),
        )
