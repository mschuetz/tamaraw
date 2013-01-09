import simples3
from tamaraw.util import load_config
import os
config = load_config()
bucket = simples3.S3Bucket(str(config['simples3']['bucket']),
                           str(config['simples3']['credentials']['aws_access_key_id']),
                           str(config['simples3']['credentials']['aws_secret_access_key']),
                           str(config['simples3']['baseurl']))

# if cache all. TODO cache selected
for s3_key, _, _, _ in bucket.listdir('images_'):
   store_key = s3_key.replace('images_', '')
   cache_fn = config['cache']['basepath'] + '/' + store_key + '.jpg'
   try:
       os.stat(cache_fn)
       print >> sys.stderr, 'not caching ' + s3_key + ' (already exists)'
   except OSError:
       # file does not exist
       print >> sys.stderr, 'caching ' + s3_key + ' as ' + cache_fn
       with open(cache_fn, 'w') as f:
           s3file = bucket.get(s3_key)
           f.write(s3file.read())
