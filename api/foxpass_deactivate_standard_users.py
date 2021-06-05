#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests
To run:
python foxpass_deactive_standard_users.py --api-key <api_key>
"""
import argparse

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'users/'


def main():
    parser = argparse.ArgumentParser(description='List users in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    args = parser.parse_args()
    header = {'Authorization': 'Token ' + args.api_key}
    r = requests.get(args.api_url + ENDPOINT, headers=header)
    r.raise_for_status()

    data = r.json()['data']
    for user in data:
        if user['is_active'] and not user['is_eng_user'] and not user['is_posix_user']:
            print(user['username'])
            requests.put(args.api_url + ENDPOINT + user['username'] + '/', headers=header, json={'is_active': False})


if __name__ == '__main__':
    main()
