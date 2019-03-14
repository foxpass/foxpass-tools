#!/usr/bin/env python

"""
This script requires the external libraries from requests
pip install requests

To run:
python foxpass_create_users.py --api-key <api_key> --csv-file <file name>

File format:
"<email address>,<username>,<password>"
eg.
test1@test.test,test1,''
test2@test.test,test2,''
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
        reader = csv.reader(f)
        for row in reader:
            try:
                email = row[0]
                username = row[1]
                password = row[2]
            except IndexError:
                continue
            data = {'email': email, 'username': username}
            r = requests.post(URL + ENDPOINT, headers=header, data=json.dumps(data))
            if r.json()['status'] == 'ok' and password not "''":
                data = {'password': password}
                r = requests.put(URL + ENDPOINT + username + '/', headers=header, data=json.dumps(data))
                print '{}: {}'.format(email, r.json())
            else:
                print '{}: {}'.format(email, r.json())


if __name__ == '__main__':
    main()
