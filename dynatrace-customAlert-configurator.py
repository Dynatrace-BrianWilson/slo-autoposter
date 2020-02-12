# =========================================================
# REQUIRED LIBRARIES
# =========================================================

import datetime
import getpass
import json
import logging
import requests
import sys
from time import sleep

# =========================================================
# REUSABLE VARIABLE DECLARATION
# =========================================================

dtTenantURL = 'https://'
constants_dict = {}
secrets_dict = {}
name_values = {}
config_data_len= 0
config_iteration = 0
config_file_path = []


# =========================================================
# FUNCTIONS
# =========================================================

def handleException(e):
    "Handles Exceptions. Prints them to console and exits the program"
    errorObject = {}
    if e.args:
        if len(e.args) == 2:
            errorObject[e.args[0]] = e.args[1]
        if len(e.args) == 1:
            errorObject["error"] = e.args[0]
    else:
        errorObject["exception"] = e
    logging.error(errorObject)
    sys.exit(1)

def validateGetResponse(apitoken, dtTenantURL, validateGetAPI):
    """ this function validates the respnse code of a specified get. Pass any GET api request, along with tenant and token, so long as the headers match.
        Future todo: make the headers an argument passed in when the function is invoked """
    validateGetURL = dtTenantURL + validateGetAPI
    validatgetresponse = requests.get(validateGetURL,headers=get_headers)
    # For known response codes, send a message. Otherwise send generic response code error in the else.
    if validatgetresponse.status_code == 200:
        logging.info(' Validation Check SUCCESSFUL')
        return
    elif validatgetresponse.status_code == 401:
        print('********************************************\n',
              '******************* FAIL *******************\n',
              '********************************************\n',
              'Status code 401 returned. Most likely cause is an invalid token.\n',
              'Please checked you copied a valid token for the supplied tenant.')
        logging.error(' Validation Check: HTTP 401 returned for %s. This is most likely due to an invalid API token for this tenant',validateGetURL)
        sys.exit(1)
    elif validatgetresponse.status_code == 403:
        print('********************************************\n',
              '******************* FAIL *******************\n',
              '********************************************\n',
              'Status code 403 returned. Most likely cause is incorrect permissions on the API token.\n',
              'Please make sure this token has the following privileges: \n',
              '- Read configuration\n',
              '- Write configuration\n',
              '- Capture request data')
        logging.error(' Validation Check: HTTP 403 returned for %s.\n   This is most likely due to incorrect permissions for the API token.\n      Please make sure this token has the following privileges: \n      - Read configuration\n      - Write configuration\n      - Capture request data', validateGetURL)
        sys.exit(1)
    else:
        print('FAIL - status code {0} returned for GET validation against {1} on Tenant {2} with the supplied API token'.format(validatgetresponse.status_code,validateGetAPI,dtTenantURL))
        logging.error(' Validation Check: HTTP %s returned for %s.', validatgetresponse.status_code, validateGetURL)
        sys.exit(1)

def gatherFileList(ParentFile):
    """ This function reads the list of files in the ParentFile to be used to create the configurations and stores them in the  config_file_path list"""
    config_file_path = []
    try:
        with open(ParentFile) as parent_file_list:
            for line in parent_file_list:
                config_file_path.extend([line.rstrip()])
    except Exception as e:
        print('Function gatherFileList: Cannot open file {}'.format(ParentFile))
        logging.error(' Function gatherFileList: Cannot open file %s', ParentFile)
        handleException(e)
    return config_file_path


def getExistingCustomAlerts(ConfigAPIEndpoint, getConfigType, NameKey2):
    """ This function runs a GET against the Custom Alerts API EndPoint and retrieves a list
    of existing IDs. The IDs are then queried one by one to get the rule name, metric and alerting scope storing them in the name_values dictionary. This list is used in functions postConfigs and confirmCustomAlertCreation.
    The purpose is to be able to check for the existence a custom alert that already has the same metrics and scope. """
    name_values = {}
    CustAlert_id_values = []
    get_existing_configs_url = dtTenantURL + ConfigAPIEndpoint
    get_configs = requests.get(get_existing_configs_url,headers=get_headers).json()
    x=1

    # get a list of custom alert IDs from the API
    for name_key in get_configs[getConfigType]:
        CustAlert_id_values.append(name_key[NameKey2])
    # for each ID returned above, get the actual name of the request naming rule 
    for CustAlert_ID in CustAlert_id_values:
        get_configs = requests.get(get_existing_configs_url+'/'+CustAlert_ID,headers=get_headers).json()
        name_values[x] = {'name': get_configs['name']}
        x += 1

    return name_values

def postCustAlerts(name_values, ConfigAPIEndpoint, config_file_path):
    config_iteration = 0
    config_data_len= len(config_file_path)
    config_url = dtTenantURL + ConfigAPIEndpoint
    while config_iteration < config_data_len:
        try:
            with open(config_file_path[config_iteration]) as the_JSON_file:
                loaded_JSON_file = json.load(the_JSON_file)
        except Exception as e:
            print('Function postCustAlerts: could not open the file {}'.format(config_file_path[config_iteration]))
            logging.error(' Function postCustAlerts: could not open the file %s', config_file_path[config_iteration])
            handleException(e)
        if loaded_JSON_file['eventType'] != 'CUSTOM_ALERT':
            logging.warning('!!!!! WARNING !!!!!! postCustAlerts: The file you tried posting, %s, is not a Custom Alert and will not be posted', loaded_JSON_file['name'])
            print('!!!!! WARNING !!!!!! postCustAlerts: The file you tried posting, {0}, is not a Custom Alert and will not be posted'.format( loaded_JSON_file['name']))

        else:
            dictinstance = 1
            found = 0
            for config in name_values:
                if loaded_JSON_file['name'] == name_values[dictinstance]['name']:
                    found += 1
                dictinstance += 1
            if found == 0:
                config_post = requests.post(config_url, data=json.dumps(loaded_JSON_file), headers=post_headers)
                logging.info(' postCustAlerts status code for %s = %s', loaded_JSON_file['name'], config_post.status_code)
                if config_post.status_code != 201:
                    logging.warning(' postCustAlerts: failed to create alert for %s. Response code = %s', loaded_JSON_file['name'],config_post.status_code)
                    print('ERROR: postConfigs: failed to create alert for {0}. Response code = {1}'.format( loaded_JSON_file['name'],config_post.status_code))
                else:
                    print('SUCCESS postCustAlerts status code for {0} = {1}'.format(loaded_JSON_file['name'], config_post.status_code))  
            else:
                logging.warning('ERROR: Custom Alert with the name %s already exists', loaded_JSON_file['name'])
                print('ERROR: Custom Alert with the name {0} already exists'.format(loaded_JSON_file['name']))

        config_iteration += 1
    return
                        
# =========================================================
# LOGGER
# =========================================================
logfile = 'log/hybris_config_' + datetime.datetime.now().strftime("%Y%m%d_%H%M%S") + '.log'
logging.basicConfig(filename=logfile,format='%(levelname)s:%(message)s',level=logging.INFO)

# =========================================================
# LOAD CONSTANTS & SECRETS files
# =========================================================
"""
The file Constants.txt contains:
    - the variable names and endpoints for the API calls used in this script
    - two URIs for the tenant settings pages where the user is instructed to look to see their handiwork
    - key valuse for reading modifying the name of a config in the config json file
    This file should only be modified if any of these constants have changed.
    The format for an entry is:
        variablename : value
    These will be split, whitespace will removed, and the values will be written to the dictionary constants_dict
"""


with open('Constants.txt') as constants_file:
    for line in constants_file:
        constant_key, constant_value = line.strip('\n').split(':', 1)
        constants_dict[constant_key.strip()] = constant_value.lstrip()

with open('secrets.txt') as secrets_file:
    for line in secrets_file:
        secrets_key, secrets_value = line.strip('\n').split(':', 1)
        secrets_dict[secrets_key.strip()] = secrets_value.lstrip()


# =========================================================
# GET TENANT URL AND API TOKEN
# =========================================================

# get user data for making API calls
# Uncomment these when ready to run for real
#apitoken = getAPIToken()
#dtTenantURL += getdtTenantURL()

apitoken = secrets_dict['dt_api_token']
dtTenantURL += secrets_dict['dt_tenant_url']

# =========================================================
# CONSTANTS
# =========================================================

get_headers = {'Accept':'application/json; charset=utf-8', 'Authorization':'Api-Token {}'.format(apitoken)}
post_headers = {'Content-Type':'application/json; charset=utf-8', 'Authorization':'Api-Token {}'.format(apitoken), 'accept': 'application/json; charset=utf-8'}
today = datetime.date.today().strftime("%Y%m%d")

# =========================================================
# WRITE INSTRUCTIONS TO LOG FILE
# =========================================================

with open(logfile, 'a') as the_log_file:
    the_log_file.write('**********************************************************************\n')
    the_log_file.write(' \n')
    the_log_file.write('This is the log file for the Dynatrace Custom Alert Configurator.\n')
    the_log_file.write('\n')
    the_log_file.write('**********************************************************************\n')
    the_log_file.write('**********************************************************************\n')

# =========================================================
# RUN A GET AGAINST THE API TO CHECK IF THE TENANT AND API TOKEN ARE VAILD
# =========================================================

print('Validating API access on the tenant')
validateGetResponse(apitoken, dtTenantURL, constants_dict['list_customsealerts_api'])
print('---Validation successful')

# =========================================================
# CREATE CUSTOM ALERT
# =========================================================

# This file contains the path to the json files of the custom alerts you want to create.

parent_file_name = 'new-custom-alerts-list.txt'
update_alerts_file_name = 'update-custom-alerts-list.json'

#Process the parent file - generate config_file_path list which is used to load JSON payloads later.

config_file_path = gatherFileList(parent_file_name)

#Check is there are custom alerts to be loaded in the custom-alerts-list.txt file.
if len(config_file_path) > 0:

#Run a GET against the list custom alerts  API to get a name list of existing custom alerts
# that already exist on the Dynatrace tenant. These will be used to check for pre-existing
# configurations of the same name.


    print('Get existing Request Naming Rules')
    name_values = getExistingCustomAlerts(constants_dict['list_customsealerts_api'], constants_dict['custom_alert_type'], constants_dict['nameKey_custom_alert_2'])
    print('---Get existing Request Naming Rules was successful')


#### Post New Custom Alerts via the API

    print('Posting Custom Alerts')
    postCustAlerts(name_values, constants_dict['post_customalerts_api'], config_file_path)
    print('Posting Custom Alerts complete')
