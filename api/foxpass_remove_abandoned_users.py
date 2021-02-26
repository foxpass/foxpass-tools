#!/usr/bin/env python3

"""
This script deactivates all users who aren't a member of any group

This script requires the external libraries from requests
pip install requests

To run:
python foxpass_remove_abandoned_users.py --api-key <api_key>
"""
from __future__ import print_function

import argparse
import json

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'users/'
DATA = {'is_active': False}


def main():
    parser = argparse.ArgumentParser(description='Deactivate Foxpass users who aren\'t a member of any group')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    args = parser.parse_args()
    users = user_list(args.api_key, args.api_url)
    for user in users:
        process_user(args.api_key, user, args.api_url)


def user_list(api_key, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.get(api_url + ENDPOINT, headers=header)

    # check to make sure request completed successfully
    r.raise_for_status()

    users = []
    for user in r.json()['data']:
        # only deactivate active users
        if user['active']:
            users.append(user['username'])

    return users


def process_user(api_key, user, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.get(api_url + ENDPOINT + user + '/groups/', headers=header)

    # check to make sure request completed successfully
    if not r.status_code == requests.codes.ok:
        r.raise_for_status()

    memberships = r.json()['data']
    if not memberships:
        deactivate_user(api_key, user, api_url)


def deactivate_user(api_key, user, api_url):
    header = {'Authorization': 'Token ' + api_key}
    r = requests.put(api_url + ENDPOINT + user + '/', headers=header, data=json.dumps(DATA))
    if r.status_code == requests.codes.ok:
        print('Deactivated {}'.format(user))
    else:
        print('Error deactivating user {}. Status code {}'.format(user, r.status_code))


if __name__ == '__main__':
    main()
