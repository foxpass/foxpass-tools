#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_list_users.py --api-key <api_key>
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
    output(r)


def output(r):
    data = r.json()['data']
    for group in data:
        print(group['username'])


if __name__ == '__main__':
    main()
