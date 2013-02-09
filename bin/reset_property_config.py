#!/usr/bin/env python
from tamaraw.util import load_config
from tamaraw.dao import ConfigDao
import sys

config = load_config()
dao_conf = [config['elasticsearch']['rawes'], config['elasticsearch']['indexname']]
ConfigDao(*dao_conf).update_property_config(ConfigDao.DEFAULT_PROPS)
print >> sys.stderr, "reset property configuration" 
