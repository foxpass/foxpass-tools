#!/usr/bin/env python

import argparse
import json
import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'groups/'

def main():
    parser = argparse.ArgumentParser(description='List groups in Foxpass')
    parser.add_argument('--key', required=True, help='Foxpass API Key')
    args = parser.parse_args()

    header = {'Authorization': 'Token ' + args.key}
    r = requests.get(URL + ENDPOINT, headers=header)
    output(r)

def output(r):
    data = json.loads(r.text)['data']
    for group in data:
        print group['name']

if __name__ == '__main__':
    main()
