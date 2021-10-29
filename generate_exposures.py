#!/usr/bin/env python
# coding: utf-8


import os
import json
import re
import yaml

import urllib.request


# open questions
# 1. deleted dashboards?
# 2. which folders do we care about?

looker_base_url='https://fishtown.looker.com'
looker_url = f'{looker_base_url}:19999'
looker_client_id = os.environ["LOOKER_CLIENT_ID"]
looker_client_secret = os.environ["LOOKER_CLIENT_SECRET"]

looker_api_login_body = {
    'client_id': looker_client_id,
    'client_secret': looker_client_secret
}

# POST request for Looker auth token
def get_token(url, body):
    body = urllib.parse.urlencode(body).encode()
    request = urllib.request.Request(url,
                                     data = body,
                                     headers = {'User-Agent': 'Mozilla/5.0',
                                                'Content-Type': 'application/x-www-form-urlencoded'})
    response = urllib.request.urlopen(request)
    data = json.loads(response.read().decode('utf-8'))
    return data['access_token']

token = get_token(url=f'{looker_url}/api/3.1/login', body=looker_api_login_body)

# GET request with bearer auth
def bearer_request(url, token=token):
    request = urllib.request.Request(url,
                                     headers = {'Authorization': f'Bearer {token}'})
    response = urllib.request.urlopen(request)

    # Return data and headers as dictionary object
    data = {}    
    data['header'] = dict(response.getheaders())
    if data['header']['Content-Type'] == 'application/sql':
        data['data'] = response.read().decode('utf-8')
    else:
        data['data'] = json.loads(response.read().decode('utf-8'))
    
    
    return data

def get_users():
    users = bearer_request(f'{looker_url}/api/3.1/users')
    # To work correctly, users must have populated name at first log in, otherwise generates 'None None'
    return {user['id']: {'name': f"{user['first_name']} {user['last_name']}", 'email': user['email']} for user in users['data'] if not user['verified_looker_employee']}

all_dashboard_data = bearer_request(url=f'{looker_url}/api/3.1/dashboards', token=token)['data']

# return all dashboard ids in a given folder id
def get_dashboards_in_folder(folder_id, all_dashboard_data=all_dashboard_data):
    return [dash_data['id'] for dash_data in all_dashboard_data if dash_data['folder']['id'] == folder_id]

def parse_tables(query_text):
    all_tables = re.findall("(?:from|join)\s+([\w\d]+\.[\w\d]+\.[\w\d]+)", query_text.lower())
    
    return [table.split('.')[2] for table in all_tables]

def get_dashboard_exposures(dashboard_list):
    users = get_users()
    dashboard_exposures = []

    for dashboard_id in dashboard_list:
        dashboard = bearer_request(url=f'{looker_url}/api/3.1/dashboards/{dashboard_id}', token=token)
        dashboard_looks = [tile['look']['query_id'] for tile in dashboard['data']['dashboard_elements'] if tile['look'] is not None]
        dashboard_queries = [tile['query']['id'] for tile in dashboard['data']['dashboard_elements'] if tile['query'] is not None]
        
        query_ids = list(set(dashboard_looks + dashboard_queries))
        
        dashboard_tables = []
        for query_id in query_ids:
            query_sql = bearer_request(url=f'{looker_url}/api/3.1/queries/{query_id}/run/sql')
            query_tables = parse_tables(query_sql['data'])
            dashboard_tables.extend(query_tables)
        
        dashboard_tables = list(set(dashboard_tables))
        
        dashboard_exposure = {
            'dashboard_id' : dashboard_id,
            'dashboard_url' : f'{looker_base_url}/dashboards/{dashboard_id}',
            'created_by' : users[dashboard['data']['user_id']],
            'query_ids' : query_ids,
            'dashboard_tables' : dashboard_tables,
            'title' : dashboard['data']['title']
        }
        
        dashboard_exposures.append(dashboard_exposure)
    
    return dashboard_exposures


def get_exposure_yml(dashboard_obj):
    model_refs = [f"ref('{table_name}')" for table_name in dashboard_obj['dashboard_tables']]
    exposure = {
            "version": 2,
            "exposures": [
                {
                    "name": dashboard_obj['title'],
                    "description": "",
                    "type": "dashboard",
                    "url": dashboard_obj['dashboard_url'],
                    "depends_on": model_refs,
                    "owner": {
                        "name": dashboard_obj['created_by']['name'] if dashboard_obj['created_by']['name'] != 'None None' else '',
                        "email": dashboard_obj['created_by']['email']
                    }
                }
            ]

        }
    return exposure

def write_exposure_yaml(dashboard_obj_list):
    for dashboard in dashboard_obj_list:
        filename = dashboard['title'].lower().replace(' ','_') + f"_looker_{dashboard['dashboard_id']}"
        if 'yaml_files' not in os.listdir():
            os.mkdir('yaml_files') 
        with open(f"yaml_files/{filename}.yaml", 'w') as target:
            yaml.dump(get_exposure_yml(dashboard), target, sort_keys=False)

