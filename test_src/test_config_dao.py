import unittest
from tamaraw.dao import ConfigDao
import rawes
import time

class TestConfigDao(unittest.TestCase):
    def setUp(self):
        self.indexname = "test_dao%s" % (time.time())
        self.dao = ConfigDao({}, self.indexname)

    def tearDown(self):
        es = rawes.Elastic()
        es.delete(self.indexname)

    def test_can_import_defaults_only_once(self):
        self.dao.import_default_props()
        self.assertRaises(Exception, self.dao.import_default_props)

    def test_import_defaults(self):
        self.dao.import_default_props()
        props = self.dao.get_property_config()
        self.assertEquals(ConfigDao.DEFAULT_PROPS, props)

    def test_auto_import_defaults(self):
        res = self.dao.es.get(self.dao.config_path())
        self.assertTrue((not res.has_key('exists')) or not res['exists'])
        props = self.dao.get_property_config()
        self.assertEquals(ConfigDao.DEFAULT_PROPS, props)
