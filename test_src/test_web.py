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
        tamaraw.image_dao.refresh_indices()
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

    def test_search(self):
        tamaraw.image_dao.create('asdf', 'TEST1', 'foo.jpg', prop_title='foo bar')
        tamaraw.image_dao.create('asdf', 'TEST2', 'foo.jpg', prop_title='baz quux')
        tamaraw.image_dao.refresh_indices()
        rv = self.app.get('/search/?query=bar')
        self.assertEquals('200 OK', rv.status)
        assert 'foo bar' in rv.data
        assert 'baz quux' not in rv.data
        rv = self.app.get('/search/?query=quux')
        self.assertEquals('200 OK', rv.status)
        assert 'foo bat' not in rv.data
        assert 'baz quux' in rv.data

    def test_browse_tags(self):
        tamaraw.image_dao.create('asdf', 'TEST1', 'foo.jpg', prop_title='foo bar',
                                 prop_tags=['alfalfa graybeard thriller cowslip'])
        tamaraw.image_dao.create('asdf', 'TEST2', 'foo.jpg', prop_title='baz quux',
                                 prop_tags=['alfalfa graybeard unleaded numerical schmaltz'])
        tamaraw.image_dao.refresh_indices()
        rv = self.app.get('/browse/prop_tags/alfalfa graybeard thriller cowslip/')
        self.assertEquals('200 OK', rv.status)
        assert 'foo bar' in rv.data
        assert 'baz quux' not in rv.data
        rv = self.app.get('/browse/prop_tags/alfalfa graybeard unleaded numerical schmaltz/')
        self.assertEquals('200 OK', rv.status)
        assert 'foo bar' not in rv.data
        assert 'baz quux' in rv.data

    def test_subscribe(self):
        self.app.post('/public/subscribe', data={'name': 'Holden Caulfield',
                                                 'email': 'holden.caulfield@vfmac.edu',
                                                 'comment':'asdf asdf'})
        self.app.post('/login', data={'username': 'admin', 'password': 'asdf'})
        rv = self.app.get('/private/comments/')
        self.assertEqual('200 OK', rv.status)
        assert 'Holden Caulfield' in rv.data
        assert 'holden.caulfield@vfmac.edu' in rv.data

if __name__ == '__main__':
    unittest.main()
