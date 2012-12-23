import re, os, json

class InvalidStoreKey(Exception):
    pass

def check_store_key(store_key):    
    if not re.match("^[0-9a-zA-Z_\-]+$", store_key):
        raise InvalidStoreKey()

def load_config():
    if os.environ.has_key('TAMARAW_CONFIG'):
        config_file = os.environ['TAMARAW_CONFIG']
    else:
        config_file = os.environ['HOME'] + '/.tamaraw.conf'
     
    with open(config_file) as f:
        return json.load(f)
