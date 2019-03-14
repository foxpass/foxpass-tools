#!/usr/bin/env python

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_create_users.py --api-key <api_key> --csv-file <file name>

File format:
"<email address>,<username>[,<password>]"
eg.
test0@test.test,test0
test1@test.test,test1,""
test2@test.test,test2,""
test3@non-domain.com,test3,abc123
"""

import argparse
import csv
import json

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'users/'


def main():
    parser = argparse.ArgumentParser(description='Create users in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--csv-file', required=True, help='.csv file with emails and usernames')
    args = parser.parse_args()
    header = {'Authorization': 'Token ' + args.api_key}
    # parse csv file
    with open(args.csv_file, 'rb') as f:
        password = None
        reader = csv.reader(f)
        for row in reader:
            try:
                email = row[0]
                username = row[1]
            except IndexError:
                continue
            data = {'email': email, 'username': username}
            r = requests.post(URL + ENDPOINT, headers=header, data=json.dumps(data))
            try:
                password = row[2]
            except IndexError:
                pass  # password is already set ot None above, don't need to do it again.
            if r.json()['status'] == 'ok' and password:
                data = {'password': password}
                r = requests.put(URL + ENDPOINT + username + '/', headers=header, data=json.dumps(data))
                print '{}: password set'.format(email)
            else:
                print '{}: {}'.format(email, r.json()['status'])


if __name__ == '__main__':
    main()
