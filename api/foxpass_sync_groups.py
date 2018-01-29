#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_sync_groups.py --api-key <api_key> --source-group <group_name> --dest-group <group_name>
"""
import argparse
import json
import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'groups/'
API = URL + ENDPOINT

def main():
    args = get_args()
    header = {'Authorization': 'Token ' + args.api_key}
    source_list = get_group_list(header, args.source_group).json()['data']
    dest_list = get_group_list(header, args.dest_group).json()['data']
    update_list = compare_list(source_list, dest_list)
    if len(dest_list) < 1:
        print "No users to update"
    else:
        for user_name in update_list:
            put_group_member(header, args.dest_group, user_name)

def get_args():
    parser = argparse.ArgumentParser(description='List users in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--source-group', required=True, help='Source group name')
    parser.add_argument('--dest-group', required=True, help='Destination group name')
    return parser.parse_args()

def get_group_list(header, group_name):
    r = requests.get(API + group_name + '/members/', headers=header)
    return r

def compare_list(source_list, dest_list):
    src_users = [user['username'] for user in source_list]
    dest_users = [user['username'] for user in dest_list]
    return [user for user in src_users if user not in dest_users]

def put_group_member(header, group_name, user_name):
    data = json.dumps({'username': user_name})
    r = requests.post(API + group_name + '/members/', headers=header, data=data)
    if r.status_code == 200:
        print '%s added to %s' % (user_name, group_name)
    else:
        print '%s failed to add to %s' % (user_name, group_name)

if __name__ == '__main__':
    main()
