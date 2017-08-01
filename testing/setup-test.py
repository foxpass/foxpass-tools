#!/usr/bin/env python

from __future__ import print_function
import argparse
import boto.ec2
import os
import re
import sys
import time

def main():
    parser = argparse.ArgumentParser(description='Run Foxpass setup script tests.')
    parser.add_argument('--ssh-key', help='SSH Key name to use when launching instance.')
    parser.add_argument('--branch', help='Github branch name to use for testing.')
    parser.add_argument('--bind-pw', help='Foxpass ldap bind password')
    parser.add_argument('--api-key', help='Foxpass API KEY for account connection.')
    args = parser.parse_args()

    # Connect to us-west-2
    ec2 = boto.ec2.connect_to_region('us-west-2')
    # AMIs we want to use
    amis = {
        'amzn-2014.09':'ami-8786c6b7',
        'amzn-2016.03':'ami-39798159',
        'centos-7':'ami-f4533694',
        'debian-8':'ami-221ea342',
        'ubuntu-12.04':'ami-05eb1165',
        'ubuntu-14.04':'ami-7c22b41c',
        'ubuntu-16.04':'ami-835b4efa'
    }

    # Set variuables for building the instances
    key = args.ssh_key
    sg = 'sg-23600845'
    it = 't2.micro'
    sub = 'subnet-4ec61216'
    branch = args.branch
    bind_pw = args.bind_pw
    api_key = args.api_key
    # Store the instance data here after launching
    instances = {}

    # Launch all of the instanes and store the name and instance id in instances{}
    for name,ami in amis.items():
        print('Launching', name)
        instances[name] = ec2.run_instances(ami,instance_type=it,subnet_id=sub,security_group_ids=[sg],key_name=key).instances[0].id

    # Connect to each instance and run the appropriate script for Foxpass
    for name,id in instances.items():
        # Get instance state and wait for it to be running
        print('Waiting for', name, 'to launch.', end='')
        sys.stdout.flush()
        status = ec2.get_only_instances(id)[0].state
        while status != 'running':
            time.sleep(5)
            status = ec2.get_only_instances(id)[0].state
            print('.', end='')
            sys.stdout.flush()
        print('', end='\n')

        # Build the command to be run remotely to configure each instance
        ip = ec2.get_only_instances(id)[0].ip_address
        dist = re.search('^\w+',name).group(0)
        ver = re.search('\d+.*',name).group(0)
        url = 'https://raw.githubusercontent.com/foxpass/foxpass-setup/%s/linux/%s/%s/foxpass_setup.py' % (branch,dist,ver)
        setup = 'foxpass_setup.py --base-dn dc=foxpass,dc=com --bind-user linux --bind-pw %s --api-key %s --ldap-uri ldaps://foxfood.foxpass.com --api-url https://foxfood.foxpass.com/api 2>/dev/null' % (bind_pw,api_key)
        command = 'wget %s 2>/dev/null && chmod 755 foxpass_setup.py && sudo ./%s' % (url,setup)

        # Every distro is a little unique, so tweeze out those differences here
        if name == 'centos-7':
            command = 'sudo yum install -y wget 2>/dev/null && wget %s 2>/dev/null && chmod 755 foxpass_setup.py && sudo ./%s' % (url,setup)
            output = ssh(ip,'centos',command)
        elif name == 'debian-8':
            output = ssh(ip,'admin',command)
        elif 'amzn' in name:
            output = ssh(ip,'ec2-user',command)
        elif 'ubuntu' in name:
            output = ssh(ip,'ubuntu',command)

# Run a command on the remote host
def ssh(ip,user,command):
    print('Running', command)
    sys.stdout.flush()
    print('Waiting for ssh')
    # Try and connect, if fail, sleep a second and try again
    while True:
        output = os.system('ssh %s -l %s "%s" 2>&1' % (ip,user,command))
        if output == 0:
            break
        else:
            print('.', end='')
            time.sleep(1)
            pass

if __name__ == '__main__':
    main()
