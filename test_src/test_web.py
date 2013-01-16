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

# TODO this only works if this set of tests is executed on its own.
# if all tests are executed via nose, the tamaraw package has most
# likely already been initialized
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
        
    def login_as_admin(self):
        return self.app.post('/login', data={'username': 'admin', 'password': 'asdf'},
                             headers={'Referer': 'http://localhost/'},
                             follow_redirects=True)

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
        rv = self.login_as_admin()
        self.assertEquals('200 OK', rv.status)
        assert 'login succesful' in rv.data

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
        self.login_as_admin()
        tamaraw.image_dao.refresh_indices()
        rv = self.app.get('/private/comments/')
        self.assertEqual('200 OK', rv.status)
        assert 'Holden Caulfield' in rv.data
        assert 'holden.caulfield@vfmac.edu' in rv.data

    def test_delete_image(self):
        self.login_as_admin()
        tamaraw.image_dao.create('asdf', 'TEST', 'foo.jpg', prop_title='test title')
        testfile = config['localstore']['basepath'] + '/TEST'
        try: 
            open(testfile, 'w').close()
            rv = self.app.post('/image/TEST/delete', follow_redirects=True)
            self.assertEqual('200 OK', rv.status)
            assert "deleted file" in rv.data
        finally:
            try:
                os.remove(testfile)
            except:
                pass

    def test_delete_image_invalid_key(self):
        self.login_as_admin()
        rv = self.app.post('/image/TEST(1+1)/delete', follow_redirects=True)
        self.assertEqual('400 BAD REQUEST', rv.status)

    def test_delete_image_redirect_to_last_collection(self):
        self.login_as_admin()
        tamaraw.image_dao.create('asdf', 'TEST', 'foo.jpg', prop_title='test title')
        with self.app.session_transaction() as sess:
            sess['last_collection'] = '/recent/'
            rv = self.app.post('/image/TEST/delete')
            self.assertEqual('302 FOUND', rv.status)
            self.assertEqual('http://localhost/recent/', rv.headers['Location'])

    def test_delete_image_without_file(self):
        self.login_as_admin()
        tamaraw.image_dao.create('asdf', 'TEST', 'foo.jpg', prop_title='test title')
        rv = self.app.post('/image/TEST/delete', follow_redirects=True)
        self.assertEqual('200 OK', rv.status)
        assert "ignorable error" in rv.data

        

if __name__ == '__main__':
    unittest.main()
