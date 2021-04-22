#!/usr/bin/env python3

"""
This script can generate dummy data into your Foxpass account including users, groups and custom fields.

Required packages:
pip install requests faker

To run:
python foxpass_dummy_data.py --api-key <api_key> --user-domain example.com --user-count 10 --group-count 2 --custom-fields address date_of_birth image_url ipv4 job mac_address ssn phone_number
"""

import argparse
import json
import random
import requests
import time

import faker


API_HOSTNAME = 'https://api.foxpass.com'
CONSOLE_PAGE_URL = 'https://console.foxpass.com/settings/config/'

api_hostname, api_key = '', ''


def log(text):
    print(text)


def send_api_request(method, endpoint, data={}):
    global api_hostname, api_key
    headers = {
        'Authorization': 'Token {}'.format(api_key)
    }
    r = requests.request(method=method, url=api_hostname + endpoint, headers=headers, data=json.dumps(data))
    if r.status_code == 200 and 'reason' not in r.json():
        return True
    else:
        log("Error - {}".format(r.json()['reason']))


def main():
    global api_hostname, api_key, faker_keys
    args = get_args()
    api_hostname = args.api_hostname
    api_key = args.api_key
    
    fake = faker.Faker('en_US')

    # check if user custom fields have been added
    if args.custom_fields and len(args.custom_fields) > 0:
        val = input("Please added these custom user fields {} in Foxpass console {} (bottom of the page). \nType OK when ready: ".format(args.custom_fields, CONSOLE_PAGE_URL))
        if not val or val.lower() != 'ok':
            exit('Please add custom fields to Foxpass console and retry.')
    # create groups, users and custom fields now
    groups = create_groups(int(args.group_count))
    users = create_users(fake, args.user_domain, int(args.user_count), groups)
    update_custom_fields(fake, users, args.custom_fields)
    log("All done!")


# Create groups
def create_groups(group_count):
    groups = []
    for _ in range(group_count):
        gid = random.randrange(1000, 2000)
        group_name = 'dummy_group_{}'.format(gid)
        data = {
            'name': group_name,
            'gid': gid,
            'is_posix_group': random.choice([True, False])
        }
        if send_api_request('POST', '/v1/groups/', data):
            log('Successfully created group {}'.format(group_name))
            groups.append(group_name)
        else:
            log('Error creating group {}'.format(group_name))
    return groups


# Create users
def create_users(fake, user_domain, user_count, groups):
    users = []
    for _ in range(user_count):
        first_name = fake.first_name()
        last_name = fake.last_name()
        username = 'dummy_user_{}'.format(first_name.lower())
        data = {
            'email': '{}@{}'.format(username, user_domain), 
            'username': username
        }
        if send_api_request('POST', '/v1/users/', data=data):
            log('Successfully created user {}'.format(username))
            users.append(username)
            
            # update user properties
            data = {
                'first_name': first_name, 
                'last_name': last_name,
                'is_active': True
            }
            send_api_request('PUT', '/v1/users/{}/'.format(username), data)
            
            # add user to a random group
            if groups and len(groups) >= 1:
                group_name = random.choice(groups)
                data = {
                    'name': group_name
                }
                if send_api_request('POST', '/v1/users/{}/groups/'.format(username, group_name), data):
                    log('Successfully added user {} to group {}'.format(username, group_name))
                else:
                    log('Error adding user {} to group {}'.format(username, group_name))
        else:
            log('Error creating user {}'.format(username))
    return users


# Add custom fields to user accounts
def update_custom_fields(fake, users, custom_fields):
    for user in users:
        cf_list = {}
        for cf in custom_fields:
            cf_list[cf] = generate_value_cf_type(cf, fake)
        
        if send_api_request('PUT', '/v1/users/{}/'.format(user), {'custom_fields': cf_list}):
            log('Successfully added custom fields {} for the user {}'.format(cf_list, user))
        else:
            log('Error adding custom fields {} for the user {}. Pls add custom user fields here first: {}'.format(cf_list, user, CONSOLE_PAGE_URL))


# Generate values based on the cf type
def generate_value_cf_type(cf, fake):
    try:
        # following will call a function named cf if that exists for faker and it's modules
        if hasattr(fake, cf):
            return str(getattr(fake, cf)())
    except:
        pass
    mapping = {
        'account': 'random_int',
        'address': 'address',
        'date': 'date',
        'dob':  'fake.date_of_birth',
        'id': 'random_int',
        'mobile': 'mobile',
        'name': 'name',
        'number': 'random_int',
        'phone': 'phone_number',
        'time': 'time',
        'uri': 'uri'
    }
    for k, v in mapping.items():
        if k in cf.lower():
            return str(getattr(fake, v)())
    return fake.lexify('?' * len(cf))


# Return the command line arguments
def get_args():
    parser = argparse.ArgumentParser(description='List users in Foxpass')
    parser.add_argument('--api-hostname', default=API_HOSTNAME, help='Foxpass API Hostname')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--user-domain', required=True, help='Email domain of the users')
    parser.add_argument('--user-count', default=10, help='Number of users to populate')
    parser.add_argument('--group-count', default=2, help='Number of users to populate')
    parser.add_argument('--custom-fields', nargs='*', default=['address', 'date_of_birth', 'image_url', 'ipv4', 'job', 'mac_address', 'ssn','phone_number'], help='Custom fields to populate')
    return parser.parse_args()


if __name__ == '__main__':
    main()
