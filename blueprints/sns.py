import awacs.sns
from awacs.aws import (
    Allow,
    Policy,
    Statement,
)
from stacker.blueprints.base import Blueprint
from troposphere import (
    iam,
    sns,
    And,
    Equals,
    Join,
    If,
    Not,
    Output,
    Ref,
)

TOPIC = 'Topic'
PUBLISHER_POLICY = 'PublisherPolicy'


class Topic(Blueprint):

    PARAMETERS = {
        'DisplayName': {
            'type': 'String',
            'description': 'The display name of the SNS topic',
            'default': '',
        },
        'Publisher': {
            'type': 'String',
            'description': 'The ARN of the user who can publish to the topic',
            'default': '',
        },
        'SubscriptionEndpoint': {
            'type': 'String',
            'description': 'Optional subscription endpoint for the topic.',
            'default': '',
        },
        'SubscriptionProtocol': {
            'type': 'String',
            'description': 'Optional subscription protocol for the topic.',
            'default': '',
        },
    }

    def create_topic(self):
        self.template.add_condition(
            'HasSubscription',
            And(
                Not(Equals(Ref('SubscriptionEndpoint'), '')),
                Not(Equals(Ref('SubscriptionProtocol'), '')),
            ),
        )
        subscription = sns.Subscription(
            Endpoint=Ref('SubscriptionEndpoint'),
            Protocol=Ref('SubscriptionProtocol'),
        )
        subscriptions = If('HasSubscription', [subscription], [])
        self.template.add_resource(
            sns.Topic(
                TOPIC,
                DisplayName=Ref('DisplayName'),
                Subscription=subscriptions,
            )
        )
        self.template.add_output(Output(TOPIC, Value=Ref(TOPIC)))

    def create_publisher_policy(self):
        self.template.add_condition(
            'HasPublisher',
            Not(Equals(Ref('Publisher'), '')),
        )
        statements = [
            Statement(
                Effect=Allow,
                Action=[awacs.sns.Publish],
                Resource=[Ref(TOPIC)],
            ),
        ]
        self.template.add_resource(
            iam.PolicyType(
                PUBLISHER_POLICY,
                PolicyName=Join('-', [PUBLISHER_POLICY, Ref('DisplayName')]),
                PolicyDocument=Policy(Statement=statements),
                Users=[Ref('Publisher')],
                Condition='HasPublisher',
            ),
        )

    def create_template(self):
        self.create_topic()
        self.create_publisher_policy()
