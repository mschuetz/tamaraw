import unittest
from StringIO import StringIO
from image_org.store import LocalStore
from image_org.store import unique_id
from image_org.dao import check_store_key

class TestLocalStore(unittest.TestCase):
    def setUp(self):
        self.store = LocalStore('/tmp')

    def test_create_and_retrieve(self):
        store_key = self.store.save(StringIO("foo"))
        with open(self.store.path(store_key)) as f:
            self.assertEquals("foo", f.read())

    def test_store_keys_are_ok_for_dao(self):
        for _ in xrange(100):
            store_key = unique_id()
            check_store_key(store_key)

if __name__ == '__main__':
    unittest.main()
