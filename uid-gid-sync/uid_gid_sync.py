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

ROOT_PATH = '/'
USER_PATH = '/etc/passwd'
GROUP_PATH = '/etc/group'

TEST_ROOT_PATH = '/home/asakapab0i/foxpass-tools/uid-gid-sync/'
TEST_USER_PATH = '/home/asakapab0i/foxpass-tools/uid-gid-sync/passwd'
TEST_GROUP_PATH = '/home/asakapab0i/foxpass-tools/uid-gid-sync/group'


def main():
    args = get_args()
    header = {'Authorization': 'Token ' + args.api_key}
    remote_users = query_api(header, USER_ENDPOINT).json()
    remote_groups = query_api(header, GROUP_ENDPOINT).json()
    local_info = get_user_group_mapping(get_user_info(), get_group_info())
    users_mapping = get_remote_local_users_mapping(remote_users['data'], local_info['users'], args.ignore_local_users)
    groups_mapping = get_remote_local_groups_mapping(remote_groups['data'], local_info['groups'])
    if len(users_mapping):
        print("Checking users and files...it may take some time please wait.\n")
        user_files = get_files_owned(users_mapping)
        pprint(user_files)
        if user_check("WARNING:\nPlease create a backup before doing so.\nPlease review the users and files that will be updated."):
            update_entity_info_and_files(user_files, args.dry_run)
        else:
            print('Skipping user and files update...')
    if len(groups_mapping):
        print("Checking groups and files...it may take some time please wait.\n")
        group_files = get_files_owned(users_mapping, type='group')
        pprint(group_files)
        if user_check("WARNING:\nPlease create a backup before doing so.\nPlease review the users and files that will be updated."):
            update_entity_info_and_files(group_files, args.dry_run)
        else:
            print('Skipping groups and files update...')


# This function will perform the update to the user and files associated from the old uid to the new uid
# It will utilize the subprocess usermod from linux so the important files will be updated properly
def update_entity_info_and_files(entities, dry_run):
    print("Updating entity and files...please wait...\n")
    for entity in entities.values():
        index = get_index_by_type(entity['type'])
        pprint(index)


# Walk the entire filesystem starting from / and find the old UID of the user in each file
# This will take some time depending how many files and folders each user owned and how big the filesystem
# Making sure that we only loop on the root directory once
# @TODO merge both users and groups so it will only have one root directory trip
def get_files_owned(entity_mapped, type='user'):
    files_mapping = {}
    for root, dirs, files, in os.walk(TEST_ROOT_PATH):
        files_mapping = check_files_iid(files, root, files_mapping, entity_mapped, type)
        files_mapping = check_files_iid(dirs, root, files_mapping, entity_mapped, type)
    return files_mapping


# Check the uid of both files and directory then append it to the main dictionary
def check_files_iid(files, root, files_mapping, entity_mapped, type):
    index = get_index_by_type(type)
    ent_arr = [ent[index['old']] for ent in entity_mapped]
    for fn in files:
        path = os.path.join(root, fn)
        if type == 'group':
            ent_id = os.lstat(path).st_gid
        else:
            ent_id = os.lstat(path).st_uid
        if ent_id in ent_arr:
            if ent_id in files_mapping.keys():
                files_mapping[ent_id]['files'].append(path)
            else:
                ent_info = [ent for ent in entity_mapped if ent[index['old']] == ent_id]
                files_mapping[ent_id] = {
                    'type': type,
                    index['new']: ent_info[0][index['new']],
                    index['old']: ent_id,
                    'files': [path]
                }
    return files_mapping


# Get the index context based on the type of entity
def get_index_by_type(type):
    old_index = 'old_uid'
    new_index = 'new_uid'
    if type == 'group':
        old_index = 'old_gid'
        old_index = 'new_gid'
    return {'old': old_index, 'new': new_index}


# Check if the remote users has a corresponding users in local
# It will create a dictionary of old UID and new UID
def get_remote_local_users_mapping(remote, local, ignore_list):
    users_mapping = []
    for l_user in local:
        if l_user['uid'] >= 1000 and l_user['username'] not in ignore_list:
            for r_user in remote:
                if l_user['username'] == r_user['username'] and l_user['uid'] != r_user['uid']:
                    users_mapping.append({
                      'username': r_user['username'],
                      'old_uid': l_user['uid'],
                      'new_uid': r_user['uid']
                    })
    return users_mapping


# Checks if the remote group has a corresponding group in local
# It will create a dictionary of old GID and new GID
def get_remote_local_groups_mapping(remote, local):
    groups_mapping = []
    for l_group in local:
        if l_group['gid'] >= 500:
            for r_group in remote:
                if l_group['group_name'] == r_group['name'] and l_group['gid'] != r_group['gid']:
                    groups_mapping.append({
                      'group_name': r_group['name'],
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
                user['member_of'].append({'group_name': group['group_name'], 'gid': int(group['gid'])})
                # Get the object of the user in the group instead of string
                group['members'].remove(user['username'])
                group['members'].append({'username': user['username'], 'uid': int(user['uid'])})
        # Delete the 'gid' to avoid confusion
        del user['gid']
    return {'users': sorted(users, key=itemgetter('uid')), 'groups': sorted(groups, key=itemgetter('gid'))}


# Get user input
def user_check(message, set_default=False):
    valid = {'yes': True, 'ye': True, 'y': True, 'no': False, 'n': False}
    if set_default:
        default = 'Y/n'
    else:
        default = 'y/N'
    confirm = input('{} ({})\n'.format(message, default)).lower()
    while True:
        if confirm == '':
            return set_default
        elif confirm in valid:
            return valid[confirm]
        else:
            confirm = input('Please respond with yes/no or y/n.\n').lower()


def get_args():
    parser = argparse.ArgumentParser(description='Synchronize the gid and uid of Foxpass users to local users')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    parser.add_argument('--ignore-local-users', default=[], help='Users to ignore when doing the operations')
    parser.add_argument('--dry-run', default=False, help='Print out the command to execute and files affected')
    return parser.parse_args()


if __name__ == "__main__":
    main()
