#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_delete_user.py --api-key <api_key> --username <user name>
"""

import argparse

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'users/'


def main():
    parser = argparse.ArgumentParser(description='Delete user in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    parser.add_argument('--username', required=True, help='Foxpass user name')
    args = parser.parse_args()
    header = {'Authorization': 'Token ' + args.api_key}
    r = requests.delete(args.api_url + ENDPOINT + args.username + '/', headers=header)
    print(r.json())


if __name__ == '__main__':
    main()
