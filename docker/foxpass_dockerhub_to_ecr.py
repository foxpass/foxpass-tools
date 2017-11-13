#!/usr/bin/env python
# Copyright (c) 2015-present, Foxpass, Inc.
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

# REQUIREMENTS:
# pip install boto3
# pip install docker

# USAGE:
# python foxpass_dockerhub_to_ecr.py

import argparse
import base64
import boto3
import docker
import json
import re

ECR = boto3.client('ecr')

def main():
    args = inputs()
    client, image = pull_foxpass(args.image_name)
    push = ecr_push(client, image, args.repository_name)
    push = json.loads('[' + re.sub('\r\n', ',', push)[:-1] + ']')
    print json.dumps(push[-1]['aux'])

def inputs():
    parser = argparse.ArgumentParser(description='Pull foxpass image from Docker Hub and push to ECR')
    parser.add_argument('--image-name', default='foxpass/foxpass:latest', help='Docker image to pull')
    parser.add_argument('--repository-name', default='foxpass', help='Name of ECR repo')
    args = parser.parse_args()
    return args

def pull_foxpass(image_name):
    try:
        client = docker.from_env()
        image = client.images.pull(image_name)
    except:
        raise
    return (client, image)

def ecr_push(client, image, repository):
    target = ecr_tag(image, repository)
    registry, password, username = ecr_login()
    login = client.login(username=username,password=password,registry=registry)
    push = client.images.push(target + ':latest')
    return push

def ecr_tag(image, repository):
    target_name = get_ecr_repo(repository)
    tag = image.tag(target_name)
    return target_name

def get_ecr_repo(repository):
    for repo in ECR.describe_repositories()['repositories']:
        if repo['repositoryName'] == repository:
            return repo['repositoryUri']

def ecr_login():
    try:
        token = ECR.get_authorization_token()['authorizationData'][0]
        user, password = base64.b64decode(token['authorizationToken']).split(':')
    except:
        raise
    return (token['proxyEndpoint'], password, user)


if __name__ == '__main__':
    main()
