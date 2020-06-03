#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_delete_group.py --api-key <api_key> --group-name <group name>
"""

import argparse

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'groups/'


def main():
    parser = argparse.ArgumentParser(description='Delete groups in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    parser.add_argument('--group-name', required=True, help='Foxpass group name')
    args = parser.parse_args()
    header = {'Authorization': 'Token ' + args.api_key}
    r = requests.delete(args.api_url + ENDPOINT + args.group_name + '/', headers=header)
    print(r.json())


if __name__ == '__main__':
    main()
