#!/usr/bin/env python
from image_org.util import load_config
from image_org.dao import UserDao
import sys

if not len(sys.argv) == 3:
    print >> sys.stderr, "USAGE: %s username password" % (__file__)
    sys.exit(1)

username = sys.argv[1]
password = sys.argv[2]

config = load_config()
dao_conf = [config['elasticsearch']['rawes'], config['elasticsearch']['indexname']]
user_dao = UserDao(*dao_conf)
res = user_dao.create_user(username, password)
print >> sys.stderr, "added user", username 
