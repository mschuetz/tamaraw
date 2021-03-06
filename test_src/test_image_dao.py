# encoding: utf-8
import unittest, time, uuid, rawes
from tamaraw.dao import ImageDao
from tamaraw.storage import unique_id
from tamaraw.util import InvalidStoreKey
from contracts.interface import ContractNotRespected

class TestImageDao(unittest.TestCase):
    def setUp(self):
        self.indexname = "test_dao%s" % (time.time())
        self.dao = ImageDao({}, self.indexname)

    def tearDown(self):
        es = rawes.Elastic()
        es.delete(self.indexname)

    def test_delete_checks_store_key_is_non_empty(self):
        """
        if the store_key can be empty, we could accidentally delete the whole collection
        """
        self.assertRaises(InvalidStoreKey, self.dao.delete, "")

    def test_contracts(self):
        # self.assertRaises(ContractNotRespected, self.dao.create, '', unique_id())
        self.assertRaises(InvalidStoreKey, self.dao.create, 'asdf', '####')
        self.assertRaises(ContractNotRespected, self.dao.search, {1:2}, 0, 1)
        self.assertRaises(ContractNotRespected, self.dao.search, {'a':2}, -1, 1)
        self.assertRaises(ContractNotRespected, self.dao.search, {'a':2}, 0, 0)
        
    def test_delete(self):
        self.dao.create("abc-def", "abc123", "foo.jpg", **{'prop$foo': 'bar'})
        self.dao.delete("abc123")
        self.assertIsNone(self.dao.get("abc123"))

    def test_create_and_retrieve(self):
        store_key = unique_id()
        upload_group = str(uuid.uuid4())
        self.dao.create(upload_group, store_key, "foo.jpg", **{'prop$foo': 'bar'})
        image = self.dao.get(store_key)
        self.assertEquals(store_key, image['store_key'])
        self.assertEquals(upload_group, image['upload_group'])
        self.assertEquals("foo.jpg", image['original_filename'])
        self.assertEquals("bar", image['prop$foo'])

    def test_get_facets(self):
        upload_group = str(uuid.uuid4())
        self.dao.create(upload_group, unique_id(), "foo1.jpg", **{'prop$foo': 'bar'})
        self.dao.create(upload_group, unique_id(), "foo2.jpg", **{'prop$foo': 'baz'})
        self.dao.refresh_indices()
        facets = self.dao.get_facets('prop$foo')
        self.assertEquals(facets['prop$foo'], {u'bar':1, u'baz':1})

if __name__ == '__main__':
    unittest.main()
