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
    },
    "show_database_link": True,
    "view_timezone": "CET"
}

# first, write the config to a temp file, then make sure the config is loaded even
# if the temp file was not read because the package was loaded by a previous test
with tempfile.NamedTemporaryFile() as f:
    json.dump(config, f)
    f.flush()
    # import tamaraw before the file is automatically deleted
    os.environ['TAMARAW_CONFIG'] = f.name
    import tamaraw
    # in case it has been loaded before:
    dao_conf = [config['elasticsearch']['rawes'], config['elasticsearch']['indexname']]
    tamaraw.config_dao = tamaraw.dao.ConfigDao(*dao_conf)
    tamaraw.comment_dao = tamaraw.dao.CommentDao(*dao_conf)
    tamaraw.image_dao = tamaraw.dao.ImageDao(*dao_conf)
    tamaraw.user_dao = tamaraw.dao.UserDao(*dao_conf)
    tamaraw.store = tamaraw.storage.LocalStore(config['localstore']['basepath'])

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

    def assertOk(self, rv):
        self.assertEquals('200 OK', rv.status)

    def assertForbidden(self, rv):
        self.assertEqual('403 FORBIDDEN', rv.status)

    def assertRedirect(self, rv):
        self.assertEqual('302 FOUND', rv.status)
        
    def login_as_admin(self):
        return self.app.post('/login', data={'username': 'admin', 'password': 'asdf'},
                             headers={'Referer': 'http://localhost/'},
                             follow_redirects=True)

    def test_smoke(self):
        rv = self.app.get('/')
        self.assertOk(rv)
        tamaraw.image_dao.create('asdf', 'TEST', 'foo.jpg', prop_title='test title')
        tamaraw.image_dao.refresh_indices()
        rv = self.app.get('/recent/')
        self.assertOk(rv)
        rv = self.app.get('/recent/o1')
        self.assertOk(rv)
        rv = self.app.get('/image/TEST')
        self.assertOk(rv)
        assert 'test title' in rv.data

    def test_login(self):
        rv = self.login_as_admin()
        self.assertOk(rv)
        assert 'login succesful' in rv.data

    def test_logout(self):
        rv = self.app.get('/private/comments/')
        self.assertForbidden(rv)
        rv = self.login_as_admin()
        self.assertOk(rv)
        rv = self.app.get('/private/comments/')
        self.assertOk(rv)
        rv = self.app.get('/logout', follow_redirects=True)
        self.assertOk(rv)
        rv = self.app.get('/private/comments/')
        self.assertForbidden(rv)

    def test_comment(self):
        tamaraw.image_dao.create('asdf', 'TEST1', 'foo.jpg', prop_title='foo bar')
        rv = self.app.post('/public/image/TEST1/comment', data={'real_name': 'Holden Caulfield',
                                                                'name': '',
                                                                'email': 'holden.caulfield@vfmac.edu',
                                                                'text':'asdf asdf'})
        self.assertRedirect(rv)
        tamaraw.comment_dao.refresh_indices()
        self.login_as_admin()
        rv = self.app.get('/private/comments/')
        self.assertOk(rv)
        assert 'Holden Caulfield' in rv.data

    def test_comment_invisible_captcha(self):
        tamaraw.image_dao.create('asdf', 'TEST1', 'foo.jpg', prop_title='foo bar')
        rv = self.app.post('/public/image/TEST1/comment', data={'name': 'Spammer',
                                                                'real_name': 'Spammer',
                                                                'email': 'holden.caulfield@vfmac.edu',
                                                                'text':'asdf asdf'})
        self.assertForbidden(rv)
        tamaraw.comment_dao.refresh_indices()
        self.login_as_admin()
        rv = self.app.get('/private/comments/')
        self.assertOk(rv)
        assert 'Spammer' not in rv.data

    def test_search(self):
        tamaraw.image_dao.create('asdf', 'TEST1', 'foo.jpg', prop_title='foo bar')
        tamaraw.image_dao.create('asdf', 'TEST2', 'foo.jpg', prop_title='baz quux')
        tamaraw.image_dao.refresh_indices()
        rv = self.app.get('/search/?query=bar')
        self.assertOk(rv)
        assert 'foo bar' in rv.data
        assert 'baz quux' not in rv.data
        rv = self.app.get('/search/?query=quux')
        self.assertOk(rv)
        assert 'foo bar' not in rv.data
        assert 'baz quux' in rv.data

    def test_browse_tags(self):
        tamaraw.image_dao.create('asdf', 'TEST1', 'foo.jpg', prop_title='foo bar',
                                 prop_tags=['alfalfa graybeard thriller cowslip'])
        tamaraw.image_dao.create('asdf', 'TEST2', 'foo.jpg', prop_title='baz quux',
                                 prop_tags=['alfalfa graybeard unleaded numerical schmaltz'])
        tamaraw.image_dao.refresh_indices()
        rv = self.app.get('/browse/tags/alfalfa graybeard thriller cowslip/')
        self.assertOk(rv)
        assert 'foo bar' in rv.data
        assert 'baz quux' not in rv.data
        rv = self.app.get('/browse/tags/alfalfa graybeard unleaded numerical schmaltz/')
        self.assertOk(rv)
        assert 'foo bar' not in rv.data
        assert 'baz quux' in rv.data

    def test_subscribe(self):
        rv = self.app.post('/public/subscribe', data={'real_name': 'Subscriber',
                                                      'name': '',
                                                      'email': 'subscriber@example.org',
                                                      'comment':'asdf asdf'})
        self.assertRedirect(rv)
        self.login_as_admin()
        tamaraw.image_dao.refresh_indices()
        rv = self.app.get('/private/comments/')
        self.assertOk(rv)
        assert 'Subscriber' in rv.data
        assert 'subscriber@example.org' in rv.data

    def test_subscribe_invisible_captcha(self):
        rv = self.app.post('/public/subscribe', data={'real_name': 'Spam Subscriber',
                                                 'name': 'Spam Subscriber',
                                                 'email': 'subscriber@example.org',
                                                 'comment':'asdf asdf'})
        self.assertForbidden(rv)
        self.login_as_admin()
        tamaraw.image_dao.refresh_indices()
        rv = self.app.get('/private/comments/')
        self.assertOk(rv)
        assert 'Spam Subscriber' not in rv.data

    def test_delete_image(self):
        self.login_as_admin()
        tamaraw.image_dao.create('asdf', 'TEST', 'foo.jpg', prop_title='test title')
        testfile = config['localstore']['basepath'] + '/TEST'
        try: 
            open(testfile, 'w').close()
            rv = self.app.post('/image/TEST/delete', follow_redirects=True)
            self.assertOk(rv)
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
        self.assertOk(rv)
        assert "ignorable error" in rv.data

if __name__ == '__main__':
    unittest.main()
