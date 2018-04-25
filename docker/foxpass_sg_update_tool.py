#! /usr/bin/env python

"""
# Copyright (c) 2018-present, Foxpass, Inc.
# All rights reserved.
#
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.

This script requires the external library boto3
pip3 install boto3

AWS role permissions required:
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "VisualEditor0",
            "Effect": "Allow",
            "Action": [
                "ec2:RevokeSecurityGroupIngress",
                "ec2:AuthorizeSecurityGroupIngress",
                "ecs:ListTaskDefinitionFamilies",
                "ecs:ListTasks",
                "ec2:DescribeSecurityGroups",
                "ec2:UpdateSecurityGroupRuleDescriptionsIngress"
            ],
            "Resource": "*"
        },
        {
            "Sid": "VisualEditor1",
            "Effect": "Allow",
            "Action": "ecs:DescribeTasks",
            "Resource": "arn:aws:ecs:*:*:task/*"
        }
    ]
}

To run:
./foxpass_sg_update_tool.py --assume <account:role> --cluster <cluster-name> --region <AWS_REGION> --security-group <sg-12345678> --task-name <task>
"""

import argparse
import boto3
import logging
import os


def main():
    args = get_args()
    cluster, sg_id, task_name = (args.cluster, args.security_group, args.task_name)
    ec2, ecs = get_AWS(args)
    security_group = ec2.SecurityGroup(sg_id)
    active_ports = get_ports(cluster, ecs, task_name)
    rules = get_current_sg_rules(security_group, task_name)
    add_ports, clear_ports = ports_to_change(active_ports, rules)
    update_security_group(add_ports, clear_ports, rules, security_group, task_name)


# In Lambda run this instead of main()
def lambda_handler(event, context):
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    ec2 = boto3.resource('ec2')
    ecs = boto3.client('ecs')
    cluster = os.environ.get('CLUSTER')
    sg_id = os.environ.get('SG_ID')
    task_name = os.environ.get('TASK_NAME')
    security_group = ec2.SecurityGroup(sg_id)
    active_ports = get_ports(cluster, ecs, task_name)
    rules = get_current_sg_rules(security_group, task_name)
    add_ports, clear_ports = ports_to_change(active_ports, rules)
    update_security_group(add_ports, clear_ports, rules, security_group, task_name)
    logger.info('Active: {}\tAdded: {}\tCleared: {}'.format(active_ports, add_ports, clear_ports))


# Return variable from command line
def get_args():
    parser = argparse.ArgumentParser(description='Update SecurityGroup for ephemeral docker ports')
    parser.add_argument('--assume', help='AWS Account and Role ie: 999999999999:update_sg')
    parser.add_argument('--cluster', required=True, help='ECS cluster name')
    parser.add_argument('--region', help='AWS Region ECS cluster is in')
    parser.add_argument('--security-group', required=True, help='SecurityGroup id')
    parser.add_argument('--task-name', required=True, help='ECS task name to update')
    return parser.parse_args()


# Assume role and return credentials data
def assume_role(assume):
    sts_client = boto3.client('sts')
    account, role = assume.split(':')
    assumedRoleObject = sts_client.assume_role(RoleArn='arn:aws:iam::%s:role/%s' % (account, role),
                                               RoleSessionName='AssumeRoleSession1')
    credentials = assumedRoleObject['Credentials']
    return credentials


# Set AWS API resrouces
def get_AWS(args):
    if args.assume and args.region:
        credentials = assume_role(args.assume)
        assume = {'aws_access_key_id': credentials['AccessKeyId'],
                  'aws_secret_access_key': credentials['SecretAccessKey'],
                  'aws_session_token': credentials['SessionToken'],
                  'region_name': args.region}
        ecs = boto3.client('ecs', **assume)
        ec2 = boto3.resource('ec2', **assume)
    elif args.assume and not args.region:
        raise Exception('If assuming a role, you must set the region')
    elif args.region and not args.assume:
        ec2 = boto3.resource('ec2', region_name=args.region)
        ecs = boto3.client('ecs', region_name=args.region)
    else:
        ec2 = boto3.resource('ec2')
        ecs = boto3.client('ecs')
    return (ec2, ecs)


# Return list of exposed ports created by ECS for task_name
def get_ports(cluster, ecs, task_name):
    task_list = ecs.list_tasks(cluster=cluster, serviceName=task_name)['taskArns']
    tasks = ecs.describe_tasks(cluster=cluster, tasks=task_list)['tasks']
    ports = [binding['hostPort'] for task in tasks for binding in task['containers'][0]['networkBindings']]
    return ports


# Update the security_group with a new rule opening the ephemeral port and tagging it with the task name
def add_ingress_rule(port, security_group, task_name):
    perms = [{'FromPort': port,
              'IpProtocol': 'tcp',
              'IpRanges': [{'CidrIp': '0.0.0.0/0', 'Description': task_name}],
              'ToPort': port}]
    response = security_group.authorize_ingress(IpPermissions=perms)


# Return list of rules active in the security group that have task_name in the description
def get_current_sg_rules(security_group, task_name):
    rules = [rule for rule in security_group.ip_permissions
             for dest in rule['IpRanges']
             if 'Description' in dest.keys()
             if task_name == dest['Description']]
    return rules


# Return two lists:
# clear_ports - a list of ports that are no longer used by ECS that need to be removed
# add_ports - a list of ports that are used by ECS that need to be added
def ports_to_change(active_ports, rules):
    sg_ports = [rule['FromPort'] for rule in rules]
    clear_ports = [port for port in sg_ports if port not in active_ports]
    add_ports = [port for port in active_ports if port not in sg_ports]
    return add_ports, clear_ports


# Create a list of rules that need to be removed based on clear_ports
# Process two lists:
# add_ports - list of ports to create new rules for
# clear_rules - list of rules to remove
def update_security_group(add_ports, clear_ports, rules, security_group, task_name):
    clear_rules = [rule for rule in rules
                   for port in clear_ports
                   if rule['FromPort'] == port]
    for rule in clear_rules:
        response = security_group.revoke_ingress(IpPermissions=[rule])
    for port in add_ports:
        add_ingress_rule(port, security_group, task_name)


if __name__ == '__main__':
    main()
