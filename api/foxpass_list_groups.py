#!/usr/bin/env python

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_list_groups.py --api-key <api_key>
"""

import argparse

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'groups/'


def main():
    parser = argparse.ArgumentParser(description='List groups in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    args = parser.parse_args()
    header = {'Authorization': 'Token ' + args.api_key}
    r = requests.get(URL + ENDPOINT, headers=header)
    output(r)


def output(r):
    data = r.json()['data']
    for group in data:
        print group['name']


if __name__ == '__main__':
    main()
