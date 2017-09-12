#!/usr/bin/env python

# aws-vault exec fp -- ./setup-test.py --ssh-key <key_name> --branch <test_branch> --bind-pw <bind_password> --api-key <foxpass_api_key>

from commands import getstatusoutput
from multiprocessing import Pool
import argparse
import logging
import multiprocessing
import os
import re
import sys
import time

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
SG = 'sg-23600845'          # Old openVPN testing SG allows port 22 and 1194
IT = 't2.nano'              # save $$$
SUB = 'subnet-4ec61216'     # This puts it in the testing VPC in us-west-2
REGION_NAME = 'us-west-2'   # if you change this you must change the AMIs above
USER = os.environ['USER']
LOGGER = multiprocessing.log_to_stderr()
LOGGER.setLevel(logging.INFO)
LOGGER.info('Starting test(s)')

def main():
    parser = argparse.ArgumentParser(description='Run Foxpass setup script tests.')
    parser.add_argument('--ssh-key', required=True, help='SSH Key name to use when launching instance.')
    parser.add_argument('--branch', required=True, help='Github branch name to use for testing.')
    parser.add_argument('--bind-pw', required=True, help='Foxpass ldap bind password')
    parser.add_argument('--api-key', required=True, help='Foxpass API KEY for account connection.')
    parser.add_argument('--ami-name', default=False, help='Distro name to run as a single instance')
    args = parser.parse_args()

    # Non-global vaiables for launching instances and running the config script
    key = args.ssh_key
    branch = args.branch
    bind_pw = args.bind_pw
    api_key = args.api_key

    # Check to see if we are running just one ami or the whole list
    if args.ami_name:
        name, ami = ami_check(args.ami_name)
        test_instance(key, branch, bind_pw, api_key, name, ami)
    else:
        multi_process(key, branch, bind_pw, api_key)

# Check ami_name
def ami_check(name):
    if name in AMIS.keys():
        return name, AMIS[name]
    else:
        LOGGER.warning('Do not know how to configure this distro, please update setup-test.py with parameters for %s.', name)
        exit()

# Run all every AMI we test
def multi_process(key, branch, bind_pw, api_key):
    # Create a process pool large enough to run all of the instances in parallel
    pool = Pool(len(AMIS))
    # Build an array with all of the parameters that get called in test_instance()
    tests = [(key, branch, bind_pw, api_key, name, ami) for name, ami in AMIS.items()]
    # Pass the parameters for each process call into star_test_instance() to expand the arguments
    for run in pool.map(star_test_instance, tests):
        r = run     # Run each process

# Expand the parameters passed in by pool.map() to test_instance()
def star_test_instance(args):
    return test_instance(*args)

# Connect to instance and run the appropriate script for Foxpass
def test_instance(key, branch, bind_pw, api_key, name, ami):
    # Connect to EC2
    ec2 = boto.ec2.connect_to_region(REGION_NAME)
    # Launch an instance and save the instance_id
    LOGGER.info('Launching %s.', name)
    instance_id = ec2.run_instances(ami, instance_type=IT, subnet_id=SUB, security_group_ids=[SG], key_name=key).instances[0].id
    # Get instance state and wait for it to be running
    instance_wait(ec2, instance_id, name)
    # Build the command to run per instance
    command, ip = build_command(ec2, instance_id, name, branch, bind_pw, api_key)
    # Run the command on each instance
    run_command(name, ip, command)
    # Test the setup!
    test_result(ip, name)

# Let each instance finish booting before trying to connect
def instance_wait(ec2, instance_id, name):
    LOGGER.info('Waiting for %s to boot.', name)
    status = ec2.get_only_instances(instance_id)[0].state
    while status != 'running':
        time.sleep(5)
        status = ec2.get_only_instances(instance_id)[0].state

# Create custom command based on instance data
def build_command(ec2, instance_id, name, branch, bind_pw, api_key):
    ip = ec2.get_only_instances(instance_id)[0].ip_address
    dist = re.search('^\w+', name).group(0)
    ver = re.search('\d+.*', name).group(0)
    url = 'https://raw.githubusercontent.com/foxpass/foxpass-setup/%s/linux/%s/%s/foxpass_setup.py' % (branch, dist, ver)
    setup = ['foxpass_setup.py',
             '--base-dn', 'dc=foxpass,dc=com',
             '--bind-user', 'linux',
             '--bind-pw', bind_pw,
             '--api-key', api_key,
             '--ldap-uri', 'ldaps://foxfood.foxpass.com',
             '--api-url', 'https://foxfood.foxpass.com/api', '2>/dev/null']
    command = 'wget %s 2>/dev/null && chmod 755 foxpass_setup.py && sudo ./%s' % (url, ' '.join(setup))
    LOGGER.info('Configuring %s.', name)
    return command, ip

def run_command(name, ip, command):
    # Every distro is a little unique, so tweeze out those differences here
    if name == 'centos-7':
        # Centos7 is the most annoying
        # wget is not installed by default, so prepend that to command
        command = 'sudo yum install -y wget 2>/dev/null &&' + command
        ssh(ip, 'centos', command)    # configure the remote host
        ssh(ip, USER, 'ls', fail=True) # need to have selinux block a curl command from foxpass_ssh_keys.sh
        # Now you can adjust selinux
        ssh(ip, 'centos', "sudo ausearch -c 'curl' --raw | audit2allow -M my-curl && sudo semodule -i my-curl.pp")
    elif name == 'centos-6.5':
        command = 'sudo yum install -y wget 2>/dev/null &&' + command
        ssh(ip, 'centos', command)
    elif 'debian' in name:
        ssh(ip, 'admin', command)
    elif 'amzn' in name:
        ssh(ip, 'ec2-user', command)
    elif 'ubuntu' in name:
        ssh(ip, 'ubuntu', command)
    else:
        LOGGER.warning('Do not know how to configure this distro, please update setup-test.py with parameters for %s.', name)

# Check to see if ldap logins and sudo work
def test_result(ip, name):
    result = re.search('root', ssh(ip, USER, 'sudo whoami', verbose=True, once=True))
    if not result:
        LOGGER.warning('%s failed, log in and investigate.', name)
    else:
        LOGGER.info('%s passed!', name)

# Run a command on a remote host
def ssh(ip, user, command, verbose=False, once=False):
    # ip = target ip address
    # user = ssh user
    # command = remote command to run
    # verbose = return the results of ssh
    # once = if True, only try once
    count = 0
    while True:
        # Attempt to run the command, capture status and output from os command
        status, output = getstatusoutput('ssh %s -l %s -t "%s"' % (ip, user, command))
        # If successful or we are only trying once, exit the loop
        if status == 0:
            if verbose:
                LOGGER.warning('Failed to run: %s', command)
                return output
            else:
                return
        if once:
            if verbose:
                return output
            else:
                return
        count += 1
        if count > 5:
            LOGGER.warning('Failed to run: %s', command)
            LOGGER.warning('SSH failed for %s after 5 attempts, investigate', ip)
            return
        time.sleep(10)
        pass

if __name__ == '__main__':
    main()
