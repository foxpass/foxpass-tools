#!/usr/bin/env python3

"""
This script removes groups that match a username and gid of a user

This script requires the external libraries from requests
pip install requests

To run:
python foxpass_remove_user_groups.py --api-key <api_key>
"""
from __future__ import print_function

import argparse

import requests

URL = 'https://api.foxpass.com/v1/'
USERS_ENDPOINT = 'users/'
GROUPS_ENDPOINT = 'groups/'


def main():
    parser = argparse.ArgumentParser(description='Removes groups that match a username and gid of a user')
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

    # check to make sure request completed successfully
    if not r.status_code == requests.codes.ok:
        r.raise_for_status()

    return r.json()['data']


def check_group_for_user(api_key, group, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.get(api_url + USERS_ENDPOINT + group['name'] + '/', headers=header)

    if r.status_code != requests.codes.ok:
        # no user with that group name
        return False

    user = r.json()['data']

    # compare gid's
    if user['gid'] != group['gid']:
        print("Group & user {}: gid does not match {}-{}".format(group['name'], group['gid'], user['gid']))
        return False

    # username matches group name and gid matches
    return True


def remove_group(api_key, group, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.delete(api_url + GROUPS_ENDPOINT + group['name'] + '/', headers=header)
    if r.status_code == requests.codes.ok:
        print('Deleted group {}'.format(group['name']))
    else:
        print('Error deleting group {}. Status code: {}'.format(group['name'], r.status_code))


if __name__ == '__main__':
    main()
