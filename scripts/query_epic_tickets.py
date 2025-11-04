#!/usr/bin/env python3
"""Query Jira for all tickets in SearchSpring epic."""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

JIRA_URL = os.getenv('JIRA_URL')
JIRA_USERNAME = os.getenv('JIRA_USERNAME')
JIRA_API_TOKEN = os.getenv('JIRA_API_TOKEN')

# Query for all tickets in SUBS-617 epic
# First try just getting tickets from project
jql = 'project=SUBS AND key>=SUBS-617 AND key<=SUBS-650 ORDER BY key'
url = f'{JIRA_URL}/rest/api/3/search'
params = {
    'jql': jql,
    'maxResults': 100,
    'fields': 'key,summary,status,created,updated'
}

response = requests.get(url, auth=(JIRA_USERNAME, JIRA_API_TOKEN), params=params)
response.raise_for_status()
data = response.json()

print(f'Total tickets found: {data["total"]}\n')
print('All tickets in SearchSpring epic:')
print('=' * 100)

for issue in sorted(data['issues'], key=lambda x: x['key']):
    key = issue['key']
    summary = issue['fields']['summary']
    status = issue['fields']['status']['name']
    created = issue['fields']['created'][:10]
    updated = issue['fields']['updated'][:10]

    print(f'{key:12} [{status:15}] {summary[:70]}')
    print(f'             Created: {created}  Updated: {updated}')
    print()

print('=' * 100)
print(f'\nTotal: {data["total"]} tickets')
