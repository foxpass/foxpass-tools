#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_user_cleanup.py --api-key <api_key>
"""
from __future__ import print_function

import argparse

import requests

# URL = 'https://api.foxpass.com/v1/'
URL = 'http://localhost:8000/api/v1/'
USERS_ENDPOINT = 'users/'
GROUPS_ENDPOINT = 'groups/'


def main():
    parser = argparse.ArgumentParser(description='Deactivate Foxpass users')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    args = parser.parse_args()

    # get list of groups
    groups = group_list(args.api_key, args.api_url)

    # go through each group and check to see if user exists
    for group in groups:
        # compare gid; if equal, delete
        if check_group_for_user(args.api_key, group, args.api_url):
            remove_group(args.api_key, group, args.api_url)


def group_list(api_key, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.get(api_url + GROUPS_ENDPOINT, headers=header)
    return r.json()['data']


def check_group_for_user(api_key, group, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.get(api_url + USERS_ENDPOINT + group['name'] + '/', headers=header)

    if r.status_code != 200:
        # no user with that group name
        return

    user = r.json()['data']

    # compare gid's
    if user['gid'] == group['gid']:
        remove_group(api_key, group, api_url)
    else:
        print("gid does not match {} {} {}".format(user['gid'], group['gid'], group['name']))


def remove_group(api_key, group, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.delete(api_url + GROUPS_ENDPOINT + group['name'] + '/', headers=header)
    if r.status_code == 200:
        print('Deleted group {}'.format(group['name']))
    else:
        print('Error deleting group {}'.format(group['name']))


if __name__ == '__main__':
    main()
