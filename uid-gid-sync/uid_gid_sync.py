from pprint import pprint
from operator import itemgetter

import argparse
import json
import os

import sys
import requests

URL = 'https://api.foxpass.com/v1/'
USER_ENDPOINT = 'users/'
GROUP_ENDPOINT = 'groups/'

USER_PATH = '/etc/passwd'
GROUP_PATH = '/etc/group'

TEST_USER_PATH = '/home/asakapab0i/foxpass-tools/uid-gid-sync/passwd'
TEST_GROUP_PATH = '/home/asakapab0i/foxpass-tools/uid-gid-sync/group'


def main():
    args = get_args()
    header = {'Authorization': 'Token ' + args.api_key}
    remote_user_data = query_api(header, USER_ENDPOINT).json()['data']
    remote_group_data = query_api(header, GROUP_ENDPOINT).json()['data']
    local_info = get_user_group_mapping(get_user_info(), get_group_info())
    users_mapping = get_remote_local_users_mapping(remote_user_data, local_info['users'])
    #groups_mapping = get_remote_local_groups_mapping(remote_group_data, local_info['groups'])

    if len(users_mapping):
        process_matched_users(users_mapping)


# Additional checks making sure we get the correct UID range (1000+)
def process_matched_users(users_mapped):
    users_check_passed = []
    for user in users_mapped:
        if user['old_uid'] >= 1000:
            users_check_passed.append(user['old_uid'])
    if len(users_check_passed):
        # Find the files owned by the old UID
        files_owned = get_files_owned(users_check_passed)
        pprint(files_owned)


# Walk the entire filesystem starting from / and find the old UID of the user in each file
# This take some time depending how many each users owned
# Making sure that we only loop on the root dir once
def get_files_owned(users):
    files_mapping = {}
    for root, dirs, files, in os.walk('/home/asakapab0i/foxpass-tools/uid-gid-sync/'):
        files_mapping = check_files_uid(files, root, files_mapping, users)
        files_mapping = check_files_uid(dirs, root, files_mapping, users)
    return files_mapping


# Check the files and append it to the main dictionary
def check_files_uid(files, root, files_mapping, users):
    for fn in files:
        path = os.path.join(root, fn)
        uid = os.lstat(path).st_uid
        if uid in users:
            if uid in files_mapping.keys():
                files_mapping[uid]['files'].append(path)
            else:
                files_mapping[uid] = {'old_uid': uid, 'files': [path]}
    return files_mapping


# Checks if the remote users has a corresponding users in local
# It will create a dictionary of old UID to new UID
def get_remote_local_users_mapping(remote, local):
    users_mapping = []
    for l_user in local:
        for r_user in remote:
            if l_user['username'] == r_user['username'] and l_user['uid'] != r_user['uid']:
                users_mapping.append({
                  'username': r_user['username'],
                  'old_uid': l_user['uid'],
                  'new_uid': r_user['uid']
                })
    return users_mapping


# Checks if the remote group has a corresponding group in local
# It will create a dictionary of old GID to new GID
def get_remote_local_groups_mapping(remote, local):
    groups_mapping = []
    for l_group in local:
        for r_group in remote:
            if l_group['group_name'] == r_group['name'] and l_group['gid'] != r_group['gid']:
                groups_mapping.append({
                  'username': r_group['username'],
                  'old_gid': l_group['gid'],
                  'new_gid': r_group['gid']
                })
    return groups_mapping


# Generic API query for getting the remote users and groups
def query_api(header, endpoint):
    args = get_args()
    try:
        r = requests.get(args.api_url + endpoint, headers=header)
        r.raise_for_status()
    except requests.exceptions.HTTPError as err:
        sys.exit(err)
    return r


# Get the local users in /etc/passwd
# @TODO cross-check with /etc/shadow
def get_user_info():
    passwd = open(TEST_USER_PATH, 'r')
    usernames = []
    for line in passwd.readlines():
        user = line.split(':')
        usernames.append({
            'username': user[0],
            'uid': int(user[2]),
            'gid': int(user[3]),
            'member_of': []
        })
    return usernames


# Get the local groups in /etc/group
# @TODO cross-check: Make sure that each default groups of users exists in /etc/groups
def get_group_info():
    grp = open(TEST_GROUP_PATH, 'r')
    groups = []
    for line in grp.readlines():
        group_info = line.split(':')
        groups.append({
            'group_name': group_info[0],
            'gid': int(group_info[2]),
            'members': group_info[3].rstrip('\n').split(',')
        })
    return groups


# Cross reference the users between groups, this includes the default group of the user in /etc/passwd
def get_user_group_mapping(users, groups):
    for user in users:
        for group in groups:
            if user['gid'] == group['gid']:
                group['members'].append(user['username'])
            if user['username'] in group['members']:
                user['member_of'].append({'gid': group['gid'], 'group_name': group['group_name']})
                # Get the object of the user in the group instead of string
                group['members'].remove(user['username'])
                group['members'].append({'username': user['username'], 'uid': int(user['uid'])})
        # Delete the 'gid' to avoid confusion
        del user['gid']
    return {'users': sorted(users, key=itemgetter('uid')), 'groups': sorted(groups, key=itemgetter('gid'))}


def get_args():
    parser = argparse.ArgumentParser(description='List users in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    return parser.parse_args()


if __name__ == "__main__":
    main()
