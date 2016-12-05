# stacks

AWS Stacks for Circle.

To bring up the stacks in an AWS region:

*Ensure you have the proper AMI mappings within `conf/circle.yml`*

```
$ stacker build -p DockerRegistryPassword=<password> -p apiRdsDb::MasterUserPassword=<password> conf/staging.env conf/circle.yml
```
