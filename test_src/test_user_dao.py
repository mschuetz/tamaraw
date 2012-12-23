# encoding: utf-8
import unittest
from tamaraw.dao import UserDao
import rawes
import time

class TestUserDao(unittest.TestCase):
    def setUp(self):
        self.indexname = "test_dao%s" % (time.time())
        self.dao = UserDao({}, self.indexname)
        self.dao.create_user("admin", "asdf")

    def tearDown(self):
        es = rawes.Elastic()
        es.delete(self.indexname)

    def test_create_and_verify(self):
        self.assertTrue(self.dao.check_credentials("admin", "asdf"))

    def test_wrong_password(self):
        self.assertFalse(self.dao.check_credentials("admin", "asdfasdf"))

    def test_non_existing(self):
        self.assertFalse(self.dao.check_credentials("afgzfdsdmin", "asdfasdf"))
