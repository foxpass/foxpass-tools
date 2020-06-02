#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_user_cleanup.py --api-key <api_key>
"""
from __future__ import print_function

import argparse
import json

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'users/'
DATA = {'is_active': False}


def main():
    parser = argparse.ArgumentParser(description='Deactivate Foxpass users')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    parser.add_argument('--keep', nargs='*', help='List of users to keep')
    args = parser.parse_args()
    users = user_list(args.api_key, args.api_url)
    keep_list = []
    keep_list.extend(args.keep)
    for user in users:
        if user not in keep_list:
            deactivate_user(args.api_key, user, args.api_url)


def user_list(api_key, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.get(api_url + ENDPOINT, headers=header)
    user_list = make_list(r.json()['data'])
    return user_list


def make_list(data):
    users = []
    for user in data:
        users.append(user['username'])
    return users


def deactivate_user(api_key, user, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.put(api_url + ENDPOINT + user + '/', headers=header, data=json.dumps(DATA))
    print('Deactivated {}'.format(user))


if __name__ == '__main__':
    main()
