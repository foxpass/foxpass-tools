#!/usr/local/bin/python3

"""
This script pulls Event logs from your Foxpass instance.

Required packages:
pip install requests

To run:
python3 foxpass_event_logs.py

By default the script will print color-coded logs from the last (7) days. You can use the optional arguments below:

--event_type - Filter by event type.
--hours - How far back to show the logs in Hours.
--csv - Output the logs to a CSV file, specify the filename and path.
"""

from datetime import datetime, timedelta, timezone
import requests
import argparse
import csv

##### EDIT THESE #####
FOXPASS_API_TOKEN = "FTA6LcR3Y7xA6cW4qeaIGeDO1YNDK1uD"

# CONSTANTS
LAST_HOW_MANY_DAYS_LOGS = 7

# "YYYY-MM-DDTHH:MMZ". STARTDATE Default 7 days ago, ENDDATE is current day/time in UTC. Can be changed with the --hours argument.
STARTDATE = (datetime.now(timezone.utc) - timedelta(days=LAST_HOW_MANY_DAYS_LOGS)).strftime('%Y-%m-%dT%H:%MZ')
ENDDATE = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%MZ')

FOXPASS_URL = "https://api.foxpass.com/v1/logs/event/"
HEADERS = {'Authorization': 'Token ' + FOXPASS_API_TOKEN}
PAGEREQUEST = requests.post(
    FOXPASS_URL,
    json={
        "from": STARTDATE,
        "to": ENDDATE,
    },
    headers=HEADERS
).json()
PAGES = PAGEREQUEST["numPages"]

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

def get_args():
    parser = argparse.ArgumentParser(description='Pull and parse Event logs from your Foxpass environment')
    parser.add_argument('--event_type', help='Filter logs by event type')
    parser.add_argument('--hours', type=int, help='How far back to check the logs in hours')
    parser.add_argument('--csv', help='Export a CSV of the log data to the specified filename and path')
    return parser.parse_args()

# Builds an if statement to filter the logs based on user arguments
def build_query(event_type=None):
    query_string = ""
    if event_type != None:
        query_string += "log['event_type']=='{}' and ".format(event_type)
    if query_string != "":
	# If the string ends with "and", remove it before returning.
        if query_string[-2] == 'd':
            query_string = query_string[:-5]
    return query_string

# Pulls logs from Foxpass and stores them
def get_logs():
    p = 0
    logs_full = []
    while p < PAGES:
        p += 1
        request = requests.post(
            FOXPASS_URL,
            json={
                "from": STARTDATE,
                "to": ENDDATE,
                "page": p,
                "ascending": True,
            }, headers=HEADERS).json()
        request_clean = request["data"]
        logs_full.append(request_clean)
    return logs_full

# Prints or exports all logs for the specified time period
def lookup_all(logs, csv_arg=None, csv_writer=None):
    p=0
    while p < PAGES:
        for log in logs[p]:
            if csv_arg == None:
                print_logs(log)
            elif csv_arg != None:
                csv_export(log, csv_writer)
        p += 1

# Prints or exports logs based on user-provided filter arguments for the specified time period
def lookup_filter(logs, if_statement, csvarg=None, csv_writer=None):
    p=0
    while p < PAGES:
        for log in logs[p]:
            if eval(if_statement) and csvarg == None:
                print_logs(log)
            elif eval(if_statement) and csvarg != None:
                csv_export(log, csv_writer)
        p += 1

def csv_export(log, csv_writer):
    csv_writer.writerow([log["timestamp"], log["event_type"], log["data"]])

# Determines start time based on the --hours argument
def start_time(hours):
    d = datetime.now(timezone.utc) - timedelta(hours=hours)
    return d.strftime('%Y-%m-%dT%H:%MZ')

def print_logs(sourcedict):
    print(
        bcolors.OKCYAN + sourcedict["timestamp"],
        bcolors.OKGREEN + sourcedict["event_type"],
        bcolors.OKBLUE + str(sourcedict["data"]),
    )

def main():
    global STARTDATE
    args = get_args()

    if args.csv != None:
        csv_open = open(args.csv, 'w', newline='')
        csv_writer = csv.writer(csv_open)
        csv_writer.writerow(["TIMESTAMP (UTC)","EVENT_TYPE","DATA"])
    else:
        csv_writer = None

    if args.hours:
        STARTDATE = start_time(args.hours)

    if_statement = build_query(args.event_type)

    logs = get_logs()

    if if_statement == "":
        lookup_all(logs, args.csv, csv_writer)
    else: 
        lookup_filter(logs, if_statement, args.csv, csv_writer)


if __name__ == '__main__':
    main()
