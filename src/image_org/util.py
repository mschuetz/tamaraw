import re

class InvalidStoreKey(Exception):
    pass

def check_store_key(store_key):    
    if not re.match("^[0-9a-zA-Z_\-]+$", store_key):
        raise InvalidStoreKey()
