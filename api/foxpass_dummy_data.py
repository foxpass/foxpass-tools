#!/usr/bin/env python3

"""
This script is used to generate fake data into the target environment.
You have to map the custom fields from the target environment to the --custom-fields parameter

pip install requests faker

To run:
python foxpass_dummy_data.py --api-key <api_key> --api-url localhost --custom_fields c l title postalCode --user-count 2
"""

import argparse
import json
import sys
import requests

from pprint import pprint
from faker import Faker

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'users/'

def main():
    args = get_args()
    faker = Faker('it_IT')
    header = {'Authorization':'Token ' + args.api_key}
    users = create_users(faker, header, args.user_domain, args.user_count, args.api_url)
    update_users(faker, header, users, args.custom_fields, args.api_url)


# Create users
def create_users(faker, header, user_domain, user_count, api_url):
    users = []
    for _ in range(user_count):
        first_name = faker.first_name()
        username = first_name.lower()
        last_name = faker.last_name()
        data = {'email': '{}@{}'.format(username, user_domain), 'username': username, 'first_name':first_name, 'last_name':last_name}
        requests.post(api_url + ENDPOINT, headers=header, data=json.dumps(data))
        users.append(data)
    return users


# Update users with the custom fields
def update_users(faker, header, users, custom_fields, api_url):
    cfields = {}
    for user in users:
        for cf in custom_fields:
            cfields[cf] = generate_value_cf_type(cf, faker)
        user['custom_fields'] = cfields
        r = requests.put("{}{}{}".format(api_url,ENDPOINT,user['username']), headers=header, data=json.dumps(user))
        print('{}: {}'.format(user['email'], r.json()))


# Generate values based on the cf type
def generate_value_cf_type(cf, faker):
    if cf == 'c':
        return faker.country()
    else:
        return faker.lexify('???????????')

# Return the command line arguments
def get_args():
    parser = argparse.ArgumentParser(description='List users in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    parser.add_argument('--user-domain', default='foxpass.com', help='Default email domain')
    parser.add_argument('--user-count', default=1, help='Number of users to populate')
    parser.add_argument('--custom-fields', nargs='*', default=[], help='Custom fields to populate')
    return parser.parse_args()


if __name__ == '__main__':
    main()
