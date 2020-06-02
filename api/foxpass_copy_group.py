#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_copy_group.py --api-key <api_key> --source-group <group_name> --dest-group <group_name>
"""
import argparse
import json
import sys

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'groups/'


def main():
    args = get_args()
    header = {'Authorization': 'Token ' + args.api_key}
    source_list = get_group_list(header, args.source_group).json()['data']
    dest_list = get_group_list(header, args.dest_group).json()['data']
    update_list = compare_list(source_list, dest_list)
    if not update_list:
        print("No users to update")
        return
    for user_name in update_list:
        put_group_member(header, args.dest_group, user_name)


# return the command line arguments
def get_args():
    parser = argparse.ArgumentParser(description='List users in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    parser.add_argument('--source-group', required=True, help='Source group name')
    parser.add_argument('--dest-group', required=True, help='Destination group name')
    return parser.parse_args()


# return a list of users in a given group
def get_group_list(header, group_name):
    args = get_args()
    try:
        r = requests.get(args.api_url + ENDPOINT + group_name + '/members/', headers=header)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        sys.exit(err)
    return r


# return list of usernames that are in source_list but not dest_list
def compare_list(source_list, dest_list):
    src_users = [user['username'] for user in source_list]
    dest_users = [user['username'] for user in dest_list]
    return set(src_users) - set(dest_users)


# add a foxpass user to a foxpass group
def put_group_member(header, group_name, user_name):
    args = get_args()
    data = json.dumps({'username': user_name})
    try:
        r = requests.post(args.api_url + ENDPOINT + group_name + '/members/', headers=header, data=data)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        print('{} failed to add to {}\n{}'.format(user_name, group_name, err))
    print('{} added to {}'.format(user_name, group_name))


if __name__ == '__main__':
    main()
