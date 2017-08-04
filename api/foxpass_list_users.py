#!/usr/bin/env python

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_list_users.py --key <api_key>
"""
import argparse
import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'users/'

def main():
    parser = argparse.ArgumentParser(description='List groups in Foxpass')
    parser.add_argument('--key', required=True, help='Foxpass API Key')
    args = parser.parse_args()

    header = {'Authorization': 'Token ' + args.key}
    r = requests.get(URL + ENDPOINT, headers=header)
    output(r)

def output(r):
    data = r.json()['data']
    for group in data:
        print group['username']

if __name__ == '__main__':
    main()
