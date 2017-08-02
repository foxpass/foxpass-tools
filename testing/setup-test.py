#!/usr/bin/env python

# aws-vault exec fp -- ./setup-test.py --ssh-key <key_name> --branch <test_branch> --bind-pw <bind_password> --api-key <foxpass_api_key>

from __future__ import print_function
from commands import getstatusoutput
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
    sg = 'sg-23600845'          # Old openVPN testing SG allows port 22 and 1194
    it = 't2.micro'             # save $$$
    sub = 'subnet-4ec61216'     # This puts it in the testing VPC in us-west-2
    # Set variables for running the setup script
    branch = args.branch
    bind_pw = args.bind_pw
    api_key = args.api_key
    user = os.environ['USER']
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
        print('Configuring', name)
        sys.stdout.flush()

        # Every distro is a little unique, so tweeze out those differences here
        if name == 'centos-7':
            # Centos7 is the most annoying
            # wget is not installed by default, so prepend that to command
            command = 'sudo yum install -y wget 2>/dev/null &&' + command
            ssh(ip,'centos',command)    # configure the remote host
            ssh(ip,user,'ls',fail=True) # need to have selinux block a curl command from foxpass_ssh_keys.sh
            # Now you can adjust selinux
            ssh(ip,'centos',"sudo ausearch -c 'curl' --raw | audit2allow -M my-curl && sudo semodule -i my-curl.pp")
        elif 'debian' in name:
            ssh(ip,'admin',command)
        elif 'amzn' in name:
            ssh(ip,'ec2-user',command)
        elif 'ubuntu' in name:
            ssh(ip,'ubuntu',command)
        else:
            print('Do not know how to configure this distro, please update setup-test.py with parameters for', name)

        # Test the setup!
        result = re.search('root',ssh(ip,user,'sudo whoami',verbose=True,fail=True))
        if not result:
            print(name, 'failed, log into', ip, 'and investigate.')
            sys.stdout.flush()
        else:
            print(name, 'passed!')
            sys.stdout.flush()

# Run a command on a remote host
def ssh(ip,user,command,verbose=False,fail=False):
    # ip = target ip address
    # user = ssh user
    # command = remote command to run
    # verbose = return the results of ssh
    # fail = if True, only try once
    count = 0
    while True:
        # Attempt to run the command, capture status and output from os command
        status, output = getstatusoutput('ssh %s -l %s -t "%s"' % (ip,user,command))
        # If successful or we are only trying once, exit the loop
        if status == 0 or fail:
            if verbose:
                return output
            else:
                return
        count += 1
        if count > 5:
            print('SSH failed for', name, 'after 5 attempts, investigate', ip)
        print('.', end='')
        sys.stdout.flush()
        time.sleep(5)
        pass

if __name__ == '__main__':
    main()
