#!/usr/bin/env python3
# Copyright (c) 2015-present, Foxpass, Inc.
# All rights reserved.
#
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.


import argparse
import datetime
import getpass
import json
import os
import stat
import subprocess

import requests

DEFAULT_BASE_URL = 'https://api.foxpass.com'


def main():
    parser = argparse.ArgumentParser(description='Create a local keypair and upload public key to Foxpass.')
    parser.add_argument('--api-url', default=DEFAULT_BASE_URL,
                        help='Foxpass API url')
    args = parser.parse_args()
    api_base = args.api_url
    email = input('Email address: ')
    password = getpass.getpass()
    # make sure the password is right
    keys = api_call(api_base, email, password, '/v1/my/sshkeys/')
    filename = create_ssh_key(email)
    add_key_to_foxpass(api_base, email, password, filename)
    print('')
    print('Don\'t forget to run ssh-add now. The -K adds the key to your keychain so it is loaded on boot:')
    print('')
    print('ssh-add -K {}'.format(filename))
    print('')


def add_key_to_foxpass(api_base, email, password, filename):
    url = '{}/v1/my/sshkeys/'.format(api_base,)
    key_name = os.path.basename(filename)
    # post public portion
    pub_filename = '{}.pub'.format(filename)
    with open(pub_filename, 'r') as key_file:
        key_content = key_file.read().strip()
    key_info = {'name': key_name,
                'key': key_content}
    api_call(api_base, email, password, '/v1/my/sshkeys/', post_data=key_info)


def create_ssh_key(email):
    home = os.environ.get('HOME')
    while True:
        date_str = datetime.datetime.now().strftime('%Y%m%d-%H%M%S')
        filename = '{}/.ssh/foxpass-ssh-{}'.format(home, date_str)
        cmd = ['ssh-keygen', '-t', 'rsa', '-b', '4096', '-C', email, '-f', filename]
        print('Enter a password for the private key')
        try:
            subprocess.check_call(cmd)
            os.chmod(filename, 0o600)
            return filename
        except Exception:
            pass


def api_call(api_base, email, password, url, post_data=None):
    final_url = api_base + url
    if post_data:
        response = requests.post(final_url, data=json.dumps(post_data), auth=(email, password))
    else:
        response = requests.get(final_url, auth=(email, password))
    resp_data = response.json()
    if 'status' in resp_data and resp_data['status'] == 'error':
        raise Exception(resp_data['message'])
    return resp_data


if __name__ == '__main__':
    main()
