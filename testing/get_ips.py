#!/usr/bin/env python

# aws-vault exec fp ./get_ips.py

import boto.ec2

# Globals
AMIS = {
    'amzn-2014.09': 'ami-8786c6b7',
    'amzn-2016.03': 'ami-39798159',
    'centos-6.5': 'ami-112cbc71',
    'centos-7': 'ami-f4533694',
    'debian-8': 'ami-221ea342',
    'ubuntu-12.04': 'ami-05eb1165',
    'ubuntu-14.04': 'ami-7c22b41c',
    'ubuntu-16.04': 'ami-835b4efa'
}
REGION_NAME = 'us-west-2'
VPC = 'vpc-af783ccb'
EC2 = boto.ec2.connect_to_region(REGION_NAME)

def main():
    for name, ami in AMIS.items():
        ips = get_ips(ami)
        print '%s instance(s):' % name
        for ip in ips:
            print ip

def get_ips(ami):
    instance_ips = []
    reservations = EC2.get_all_instances(filters={'image-id':ami, 'vpc-id': VPC})
    for reservation in reservations:
        for instance in reservation.instances:
            instance_ips.append(instance.ip_address)
    return instance_ips

if __name__ == '__main__':
    main()
