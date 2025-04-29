#!/usr/bin/env python3

"""
This script requires the external libraries from requests
pip install requests
To run:
python foxpass_create_mac_addresses.py --api-key <api_key> --csv-file <file name>

CSV format should be:

entry_name,mac_address,description
Johns Devices,00:11:22:33:44:55,MacBook Pro
Johns Devices,AA:BB:CC:DD:EE:FF,John’s iPad
Sarahs Devices,11:22:33:44:55:66,Dell Laptop
Sarahs Devices,22:33:44:55:66:77,Surface Pro
Michaels Devices,33:44:55:66:77:88,iPhone
"""

import argparse
import csv
import json

import requests

URL = 'https://api.foxpass.com/v1/'
ENDPOINT = 'mac_entries/'

def create_mac_entry(headers, entry_name):
    payload = {
        'name': entry_name
    }

    response = requests.post(f"{URL}{ENDPOINT}", json=payload, headers=headers)
    print(response)
    if response.status_code == 200:
        print(f'Created a mac entry: {entry_name}')
    else:
        print(f'Failed to create a mac entry: {entry_name}')

    return entry_name

def add_mac_to_entry(headers, entry_name, mac_address):
    payload = {
        "entryname": entry_name,
        "prefix": mac_address
    }

    response = requests.put(f"{URL}{ENDPOINT}{entry_name}/prefixes/", json=payload, headers=headers)

    if response.status_code == 200:
        print(f'Created a mac address entry: {entry_name}: {mac_address}')
    else:
        print(f'Failed to create a mac address entry: {entry_name}: {mac_address}')

def main():
    parser = argparse.ArgumentParser(description='Create mac entries in Foxpass')
    parser.add_argument('--api-key', required=True, help='Foxpass API Key')
    parser.add_argument('--api-url', default=URL, help='Foxpass API Url')
    parser.add_argument('--csv-file', required=True, help='.csv file with mac address and name')
    args = parser.parse_args()

    headers = {
        'Authorization': f'Token {args.api_key}',
        'Content-Type': 'application/json'
    }

    mac_data = []

    # parse csv file
    with open(args.csv_file, 'r') as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                # create the mac entry and then add the prefixes
                create_mac_entry(headers, row.get('entry_name'))
                add_mac_to_entry(headers, row.get('entry_name'), row.get('mac_address'))
            except IndexError:
                continue

if __name__ == '__main__':
    main()
