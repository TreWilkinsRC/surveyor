import os
import sys
import logging
import re
from datetime import *

# regular expression that detects ANSI color codes
from tqdm import tqdm

ansi_escape_regex = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', re.VERBOSE)

EDR_DEETS = {
    'cbc': {
        "full_name": "VMware Carbon Black Cloud Enterprise EDR (CBC)",
        "required_credentials": "VMware Carbon Black Cloud Enterprise EDR requires a URL, token, and org_key or a credential file located following the documentation at: https://github.com/redcanaryco/surveyor/wiki/Getting-started",
        "product_arguments":['device_group', 'device_policy']
    },
    'cbr': {
        "full_name": "VMware Carbon Black EDR (CBr)",
        "required_credentials": "VMware Carbon Black EDR requires a URL and token or a credential file located following the documentation at: https://github.com/redcanaryco/surveyor/wiki/Getting-started",
        "product_arguments": ['sensor_group']
    },
    'cortex': {
        "full_name": "Cortex XDR (Cortex)",
        "required_credentials": "Cortex XDR requires a URL, api_key, api_key_id, and auth_type or a credential file and profile to be passed",
        "product_arguments": None
    },
    'dfe': {
        "full_name": "Microsoft Defender for Endpoint (DFE)",
        "required_credentials": "Microsoft Defender for Endpoint requires a token or all of 'tenantId', 'appId', and 'appSecret', or a credential file and profile to be passed",
        "product_arguments": None
    },
    's1': {
        "full_name": "SentinelOne (S1)",
        "required_credentials": "SentinelOne requires a URL and token and one of the following site_ids, account_ids, or account_names, or a credential file and profile to be passed",
        "product_arguments": ['deep_visibility']
    }
}

def _strip_ansi_codes(message: str) -> str:
    """
    Strip ANSI sequences from a log string
    """
    return ansi_escape_regex.sub('', message)


def log_echo(message: str, log: logging.Logger, level: int = logging.DEBUG, use_tqdm: bool = False):
    """
    Write a command to STDOUT and the debug log stream.
    """
    color_message = message

    if level == logging.WARNING:
        color_message = f'\u001b[33m{color_message}\u001b[0m'
    elif level >= logging.ERROR:
        color_message = f'\u001b[31m{color_message}\u001b[0m'

    if use_tqdm:
        tqdm.write(color_message)
    else:
        print(message)

    # strip ANSI sequences from log string
    log.log(level, _strip_ansi_codes(message))


def datetime_to_epoch_millis(date: datetime) -> int:
    """
    Convert a datetime object to an epoch timestamp in milliseconds.
    """
    return int((date - datetime.utcfromtimestamp(0)).total_seconds() * 1000)

def credential_builder(args) -> dict:
    cbr_creds =  {'profile': "default"} # CBr authentication requires a url and token or a credential file containing both.
    cbc_creds =  {'profile': "default"} # CBC authentication requires a url, token, and org_key or a credential file containing all.
    cortex_creds = {'profile': "", "auth_type": "standard", "tenant_ids": [], "creds_file": ""} # Cortex authentication requires api_key, url, api_key_id, and auth_type or a credential file containing all.
    dfe_creds =  {'profile': "", "creds_file": ""} # DFE authentication must include a token or the fields tenantId, appId, and appSecret values or a credential file containing all.
    s1_creds = {'profile': "", "site_ids": [], "account_ids": [], "account_names": [], "creds_file": ""} # S1 authentication requires url, token and a list containing that provides a site_id(s), account_id(s), or account_name(s) or a credential file containing all.
        
    # CBC
    if args.edr == 'cbc':
        if args.profile:
            cbc_creds['profile'] = args.profile
            
        return cbc_creds
    
    # CBr
    if args.edr == 'cbr':
        if args.profile:
            cbr_creds['profile'] = args.profile
            
        return cbr_creds
        
    if not (args.creds and args.profile) and args.edr in ['cortex', 'dfe', 's1']:
            sys.exit("Cortex, S1, and DFE need to be passed the location to a credentials file, and a profile")
            return {}
        
    # Cortex
    if args.edr == 'cortex':
        cortex_creds['profile'] = args.profile
        cortex_creds['creds_file'] = args.creds    
        
        if args.auth_type:
            cortex_creds['auth_type'] = args.auth_type.lower()
        if args.tenant_ids:
            cortex_creds['tenant_ids'] = args.tenant_ids
        
        return cortex_creds
            
    # DFE
    if args.edr == "dfe":
        dfe_creds['profile'] = args.profile
        dfe_creds['creds_file'] = args.creds
        
        return dfe_creds
    
    # S1
    if args.edr == "s1":
        s1_creds['profile'] = args.profile
        s1_creds['creds_file'] = args.creds
        
        if args.site_ids:
            s1_creds['site_ids'] = args.site_ids
            
        if args.account_ids:
            s1_creds['account_ids'] = args.account_ids
            
        if args.account_names:
            s1_creds['account_names'] = args.account_names
        
        return s1_creds

def product_arg_builder(args) -> dict:
    # Takes in argparse arguements and creates product arguments by applicable edr
    
    cbr_product_args =  {"sensor_group": None} #list
    cbc_product_args = {"device_group": None,"device_policy": None} #list and str
    s1_product_args = {"deep_visibility": None} #str

    #CBC
    if args.edr == 'cbc':
        if args.device_group:
            cbc_product_args['device_group'] = args.device_group
        
        if args.device_policy:
            cbc_product_args['device_policy'] = args.device_policy
        
        cbc_product_args = {k:v for k,v in cbc_product_args.items() if v != None}
        return cbc_product_args
    
    #CBr
    if args.sensor_group:
        cbr_product_args['sensor_group'] = args.sensor_group
        cbr_product_args = {k:v for k,v in cbr_product_args.items() if v != None}
        return cbr_product_args
        
    #S1
    if args.dv:
        s1_product_args['deep_visibility'] = True
        s1_product_args = {k:v for k,v in s1_product_args.items() if v != None}
        return s1_product_args
    
    return {}

def build_survey(args, edr: str) -> dict:
        survey_payload = {'prefix': None, 'days': None, 'minutes': None, 'limit': None, 'hostname': None, 'username': None, 'query': None, 'output': None, 'no_file': True, 'no_progress': False, 'log_dir': None, "log": None, "ioc_list": None, "ioc_source": None, "ioc_type": None, "definitions" : None, "sigma_rules": None, "products_args": None, "output_format": "csv"}

        for k,v in args.__dict__.items():
            if k in list(survey_payload.keys()):
                survey_payload[k] = v if v != None else survey_payload.pop(k)

        if args.iocfile and args.ioctype is None:
            sys.exit("--iocfile requires --ioctype")

        if args.iocfile and not os.path.isfile(args.ioc_file):
            sys.exit('Supplied --iocfile is not a file')

        if (args.output or args.prefix) and args.no_file:
            sys.exit('--output and --prefix cannot be used with --no-file')

        if args.days and args.minutes:
            sys.exit('--days and --minutes are mutually exclusive')

        if (args.sigmarule or args.sigmadir) and edr == 'cortex':
            sys.exit('Neither --sigmarule nor --sigmadir are supported by product "cortex"')

        if (args.sigmarule or args.sigmadir) and edr == 's1' and not args.dv:
            sys.exit('Neither --sigmarule nor --sigmadir are supported by SentinelOne PowerQuery')

        if args.sigmarule and not os.path.isfile(args.sigmarule):
            sys.exit('Supplied --sigmarule is not a file')

        if args.sigmadir and not os.path.isdir(args.sigmadir):
            sys.exit('Supplied --sigmadir is not a directory')

        log = logger(edr=args.edr,logs_dir=args.log_dir)

        definition_files = list()
        definitions = dict()
        sigma_rules = list()

        # test if deffile exists
        # deffile can be resolved from 'definitions' folder without needing to specify path or extension
        if args.deffile:
            if not os.path.exists(args.deffile):
                repo_deffile: str = os.path.join(os.path.dirname(__file__), 'definitions', args.deffile)
                if not repo_deffile.endswith('.json'):
                    repo_deffile = repo_deffile + '.json'

                if os.path.isfile(repo_deffile):
                    log.debug(f'Using repo definition file {repo_deffile}')
                    args.deffile = repo_deffile
                else:
                    sys.exit("The deffile doesn't exist. Please try again.")
            definition_files.append(args.deffile)

        # if --defdir add all files to list
        if args.defdir:
            if not os.path.exists(args.defdir):
                sys.exit("The defdir doesn't exist. Please try again.")
            else:
                for root_dir, dirs, files in os.walk(args.defdir):
                    for filename in files:
                        if os.path.splitext(filename)[1] == '.json':
                            definition_files.append(os.path.join(root_dir, filename))

        if definitions: survey_payload['definitions'] = definitions

        # add sigmarule to list
        if args.sigmarule:
            sigma_rules.append(args.sigmarule)

        # if --sigmadir, add all files to sigma_rules list
        if args.sigmadir:
            for root_dir, dirs, files in os.walk(args.sigmadir):
                for filename in files:
                    if os.path.splitext(filename)[1] == '.yml':
                        sigma_rules.append(os.path.join(root_dir, filename))

        if sigma_rules: survey_payload['sigma_rules'] = sigma_rules

        # run search based on IOC file
        if args.iocfile:
            with open(args.iocfile) as ioc_file:
                basename = os.path.basename(args.iocfile)
                ioc_source = basename
                data = ioc_file.readlines()
                ioc_list = [x.strip() for x in data]

            survey_payload.update({"ioc_source": ioc_source, "ioc_list": ioc_list, "ioc_type": args.ioctype})

        survey_payload['product_args'] = product_arg_builder(args=args)

        survey_payload = {k:v for k,v in survey_payload.items() if v != None}
        return survey_payload
    
def logger(edr:str, logs_dir:str='logs') -> logging.Logger:
    # instantiate a logger
    log = logging.getLogger('surveyor')
    logging.debug(f'Product: {edr}')

    # configure logging
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.handlers = list()  # remove all default handlers
    log_format = '[%(asctime)s] [%(levelname)-8s] [%(name)-36s] [%(filename)-20s:%(lineno)-4s] %(message)s'

    # create logging directory if it does not exist
    os.makedirs(logs_dir, exist_ok=True)

    # create logging file handler
    log_file_name = datetime.utcnow().strftime('%Y%m%d%H%M%S') + f'.{edr}.log'
    handler = logging.FileHandler(os.path.join(logs_dir, log_file_name))
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(logging.Formatter(log_format))
    root.addHandler(handler)
    
    return log

def check_product_args_structure(edr: str, product_args: dict) -> dict:
    edr_details = EDR_DEETS[edr]
    base = {
        "result": False,
        "edr": edr_details['full_name'],
        "required_fields": edr_details['product_arguments'],
        "incompatible_arguments": None
    }
    
    if not product_args:
        base.update({"result": True, "required_fields": "No arguments were supplied"})
        return base

    product_check = set(product_args.keys())
    required_fields_set = set(edr_details['product_arguments'])
    
    incompatible_arguments = required_fields_set - product_check
    compatible_arguments = required_fields_set & product_check

    if compatible_arguments:
        base['result'] = True
    if incompatible_arguments:
        base['incompatible_arguments'] = incompatible_arguments

    return base

def check_credentials_structure(edr: str, creds: dict) -> dict:
    # Check if the bare minimum arguments for execution are provided in the credentials.
    # This function checks for the presence of needed arguments; it does not validate input.

    cred_check = [k for k, v in creds.items() if v]
    state = False

    if edr in ["cbc", "cbr"] and 'creds_file' in cred_check:
        return {"result": True, "edr": edr, "required_fields": EDR_DEETS[edr]["required_credentials"]}

    if 'creds_file' in cred_check and 'profile' in cred_check:
        state = True
        return {"result": state, "edr": edr, "required_fields": "A profile and path to a credentials file argument have been supplied"}

    if edr == "cbc" and all(field in cred_check for field in ['url', 'token', 'org_key']):
        state = True
    elif edr == "cbr" and all(field in cred_check for field in ['url', 'token']):
        state = True
    elif edr == "cortex" and all(field in cred_check for field in ['api_key', 'url', 'api_key_id', 'auth_type']):
        state = True
    elif edr == "dfe" and ('token' in cred_check or all(field in cred_check for field in ['tenantId', 'appId', 'appSecret'])):
        state = True
    elif edr == "s1" and all(field in cred_check for field in ['url', 'token']) and any(field in cred_check for field in ['site_ids', 'account_ids', 'account_names']):
        state = True
    elif not EDR_DEETS.get(edr,None):
        return {"result": state, "edr": f"{edr} is not a supported EDR", "required_fields": None}

    return {"result": state, "edr": edr, "required_fields": EDR_DEETS[edr]["required_credentials"]}