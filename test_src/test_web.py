import time
import os
import tempfile
import json
import rawes

config = {
    "language": "de",
    "store": "local",
    "session_secret": "asdf",
    "localstore": {"basepath": tempfile.mkdtemp()},
    "elasticsearch": {
        "rawes": {
            "url": "localhost:9200",
            "timeout": 10
        },
        "indexname": "test_dao%s" % (time.time())
    }
}
with tempfile.NamedTemporaryFile() as f:
    json.dump(config, f)
    f.flush()
    # import tamaraw before the file is automatically deleted
    os.environ['TAMARAW_CONFIG'] = f.name
    import tamaraw

import unittest
import logging

class TamarawTestCase(unittest.TestCase):

    def setUp(self):
        tamaraw.app.logger.setLevel(logging.DEBUG)
        self.app = tamaraw.app.test_client()
        tamaraw.user_dao.create_user('admin', 'asdf')

    def tearDown(self):
        es = rawes.Elastic()
        es.delete(config['elasticsearch']['indexname'])

    def test_smoke(self):
        rv = self.app.get('/')
        self.assertEquals('200 OK', rv.status)
        tamaraw.image_dao.create('asdf', 'TEST', 'foo.jpg', prop_title='test title')
        rv = self.app.get('/recent/')
        self.assertEquals('200 OK', rv.status)
        rv = self.app.get('/recent/o1')
        self.assertEquals('200 OK', rv.status)
        rv = self.app.get('/image/TEST')
        self.assertEquals('200 OK', rv.status)
        assert 'test title' in rv.data

    def test_login(self):
        # currently the login controller redirects to the referrer which is a full url and not supported by the flask testclient
        rv = self.app.post('/login', data={'username': 'admin', 'password': 'asdf'})
        #                   follow_redirects=True)
        self.assertEquals('302 FOUND', rv.status)
        # assert 'login succesful' in rv.data
        

if __name__ == '__main__':
    unittest.main()
