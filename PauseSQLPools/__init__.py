import logging
import azure.functions as func
import requests
import msal

# get credentials for accessing the resources
SERVICE_PRINCIPAL_ID = '<SERVICE_PRINCIPAL_ID>'
SERVICE_PRINCIPAL_SECRET = '<SERVICE_PRINCIPAL_SECRET>'
TENANT_ID = '<TENANT_ID>'
CREDENTIALS = (f'{SERVICE_PRINCIPAL_ID}', f'{SERVICE_PRINCIPAL_SECRET}')

# list all subscriptions IDs and store them in a list
sub1_id = ''
sub2_id = ''

subs = [sub1_id, sub2_id]


def get_servers(header, subs, resource_name):
    servers_list = []

    url = f'https://management.azure.com/subscriptions/{subs}/resourceGroups/' \
          f'{resource_name}/providers/Microsoft.Sql/' \
          f'servers?api-version=2017-03-01-preview'
    response = requests.get(url, headers=header)

    res = response.json()
    for server in res['value']:
        server_name = server['name']
        servers_list.append(server_name)

    return servers_list


def get_database(header, subs, resource_name, server_names):
    list_database = []
    # print(resource_name)

    for server_name in server_names:
        url = f'https://management.azure.com/subscriptions/{subs}/resourcegroups/' \
              f'{resource_name}/providers/Microsoft.Sql/servers/{server_name}' \
              f'/databases?api-version=2020-08-01-preview'

        response = requests.get(url, headers=header)
        res = response.json()

        for name in res['value']:
            database_name = name['name']
            if database_name == 'master':
                pass
                # print(f'{resource_name}={server_name} = {database_name}')
            else:
                ready_dict = {'subs': '', 'resource_group_name': '', 'server_name': '', 'database_name': '',
                              'status': ''}
                ready_dict['subs'] = subs
                ready_dict['resource_group_name'] = resource_name
                ready_dict['server_name'] = server_name
                ready_dict['database_name'] = database_name
                status = get_status_database(header, subs, resource_name, server_name, database_name)
                ready_dict['status'] = status
                list_database.append(ready_dict)

        return list_database


def get_status_database(header, subs, resource_name, serverName, database_name):
    status = []
    url = f'https://management.azure.com/subscriptions/{subs}' \
          f'/resourcegroups/{resource_name}/providers/Microsoft.Sql/servers/{serverName}' \
          f'/databases/{database_name}?api-version=2020-08-01-preview'
    response = requests.get(url, headers=header)
    res = response.json()
    # print(res)
    # database_name = res['name']
    status = res['properties']['status']

    return status

class GetToken:
    def __init__(self, my_client, SERVICE_PRINCIPAL_SECRET, TENANT_ID):
        self.TENANT_ID = TENANT_ID
        self.SERVICE_PRINCIPAL_SECRET = SERVICE_PRINCIPAL_SECRET
        self.my_client = my_client

    def acquire_token(self):
        """
        Acquire token via MSAL
        """
        authority_url = f'https://login.microsoftonline.com/{self.TENANT_ID}'
        app = msal.ConfidentialClientApplication(
            authority = authority_url,
            client_id = self.my_client,
            client_credential = self.SERVICE_PRINCIPAL_SECRET
        )
        # https://management.azure.com/
        # https://graph.microsoft.com/.default
        # https://login.microsoftonline.com/common/oauth2/nativeclient
        token = app.acquire_token_for_client(scopes=["https://management.azure.com/.default"])

        return token['access_token']


class GetResoursesGroups:
    def __init__(self, header, subs):
        self.header = header
        self.subs = subs
        self.resource_groups = []
        self.resource_groups_with_servers = []
        self.res_servers_database_status = []

    def get_resource_groups(self):
        resource_group = []
        url = f'https://management.azure.com/subscriptions/{self.subs}/resourceGroups?api-version=2020-01-01'
        response = requests.get(url, headers=self.header)
        res = response.json()
        for i in res['value']:
            self.resource_groups.append(i['name'])
        # print(i['name'])

        return self.resource_groups

    def getServers(self):
        for i in self.resource_groups:
            my_dic = {'res_name': '', 'sql_servers': []}
            data = get_servers(header, self.subs, i)
            if len(data) > 0:
                my_dic['res_name'] = i
                my_dic['sql_servers'].extend(data)
                self.resource_groups_with_servers.append(my_dic)
        return self.resource_groups_with_servers

    def get_status_database(self):
        for i in self.resource_groups_with_servers:
            data = get_database(header, self.subs, i['res_name'], i['sql_servers'])
            if len(data) == 0:
                pass
            else:
                self.res_servers_database_status.extend(data)

        return self.res_servers_database_status

    def pause_database(self):
        collect_response = []
        for i in self.res_servers_database_status:
            if i['status'] == 'Online':
                url = f'https://management.azure.com/subscriptions/{self.subs}/resourceGroups/{i["resource_group_name"]}' \
                      f'/providers/Microsoft.Sql/servers/{i["server_name"]}/databases' \
                      f'/{i["database_name"]}/pause?api-version=2020-11-01-preview'
                response = requests.post(url, headers=header)
                collect_response.append(response.json())

        return collect_response
    

get_token = GetToken(SERVICE_PRINCIPAL_ID, SERVICE_PRINCIPAL_SECRET, TENANT_ID)
token = get_token.acquire_token()
header = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}

def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info('Python HTTP trigger function processed a request.')

    for sub in subs:
        res = GetResoursesGroups(header, sub)
        res.get_resource_groups()
        res.getServers()
        res.get_status_database()
        res.pause_database()
    
    return func.HttpResponse(
             f"Execution success",
             status_code = 200
        )
