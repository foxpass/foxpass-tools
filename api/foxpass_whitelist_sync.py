#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_whitelist_sync.py --api-key <api_key> --hostname <DDNS_hostname> --whitelist-name <whitelist_name>
"""
import argparse
import json
import socket
import sys

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'whitelist_ips/'
API = URL + ENDPOINT


def main():
    args = get_args()
    header = {'Authorization': 'Token ' + args.api_key}
    whitelist_ip = get_whitelist_ip(header, args.whitelist_name)
    target_ip = socket.gethostbyname(args.hostname)
    if whitelist_ip != target_ip:
        clear_whitelist(header, args.whitelist_name)
        set_whitelist_ip(header, args.whitelist_name, target_ip)
    else:
        print('{} is already set to {}.'.format(args.whitelist_name, target_ip))


def get_whitelist_ip(header, whitelist):
    try:
        r = requests.get(API + whitelist + '/', headers=header)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        sys.exit(err)
    return r.json()['data']['ip_address']


def set_whitelist_ip(header, whitelist, target_ip):
    data = json.dumps({'name': whitelist, 'ip_address': target_ip})
    try:
        r = requests.post(API, headers=header, data=data)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        sys.exit('Failed to update {}.\n{}'.format(whitelist, err))
    print('{} set to {}.'.format(whitelist, target_ip))


def clear_whitelist(header, whitelist):
    try:
        r = requests.delete(API + whitelist + '/', headers=header)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        sys.exit('Failed to delete {}, exiting.'.format(whitelist))
    print('Cleared {}.'.format(whitelist))


def get_args():
    parser = argparse.ArgumentParser(description='Sync Foxpass LDAP whitelist with DDNS ip')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--hostname', required=True, help='Hostname to set whitelist to')
    parser.add_argument('--whitelist-name', required=True, help='Name of whitelist in Foxpass')
    return parser.parse_args()


if __name__ == '__main__':
    main()
