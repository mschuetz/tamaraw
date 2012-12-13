import unittest
from StringIO import StringIO
from image_org.store import LocalStore

class TestLocalStore(unittest.TestCase):
    def setUp(self):
        self.store = LocalStore('/tmp')

    def test_create_and_retrieve(self):
        store_key = self.store.save(StringIO("foo"))
        with open(self.store.path(store_key)) as f:
            self.assertEquals("foo", f.read())

if __name__ == '__main__':
    unittest.main()
