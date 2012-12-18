import rawes, re
from datetime import datetime
from dateutil import tz
from contracts import contract

def range_query(field, _from, to):
    return {'range': {field: {'from': _from, 'to': to}}}

class InvalidStoreKey(Exception):
    pass

def check_store_key(store_key):    
    if not re.match("^[0-9a-zA-Z_\-]+$", store_key):
        raise InvalidStoreKey()

class ConfigDao:
    DEFAULT_PROPS = {u"prop$title": {u"de": u"Kurztitel", u"default": True},
                     u"prop$source": {u"de": u"Quelle", u"default": True},
                     u"prop$master": {u"de": u"Vorlage", u"default": True},
                     u"prop$description": {u"de": u"Bildbeschreibung", u"default": True},
                     u"prop$source_description": {u"de": u"Originalbildunterschrift", u"default": True},
                     u"prop$creation_year": {u"de": u"Aufnahmejahr", u"default": True},
                     u"prop$location": {u"de": u"Aufnahmeort", u"default": True},
                     u"prop$tags": {u"de": u"Sachbegriffe", u"default": True}}

    def __init__(self, rawes_params, indexname):
        self.es = rawes.Elastic(**rawes_params)
        self.indexname = indexname
        self.property_config = None

    def config_path(self):
        return '%s/property_config/props' % (self.indexname)
    
    def import_default_props(self):
        res = self.es.get(self.config_path())
        if res.has_key('exists') and res['exists']:
            raise Exception("property config must not exist yet")
        self.es.put(self.config_path(), data=ConfigDao.DEFAULT_PROPS)
    
    @contract(config='dict(str: *)')
    def update_property_config(self, config):
        self.es.put(self.config_path(), data=config)
    
    @contract(returns='dict(unicode: *)')    
    def get_property_config(self):
        if self.property_config != None:
            return self.property_config
        res = self.es.get(self.config_path())
        if not res.has_key('exists') or not res['exists']:
            self.import_default_props()
            return ConfigDao.DEFAULT_PROPS
        else:
            return res['_source']

class ImageDao:
    def __init__(self, rawes_params, indexname):
        self.es = rawes.Elastic(**rawes_params)
        self.indexname = indexname

    @contract(rawes_result='dict(unicode: *)', returns='list')
    def map_search_results(self, rawes_result):
        return [dict(store_key=hit['_id'], **hit['_source']) for hit in rawes_result['hits']['hits']]

    @contract(data='dict(str: *)', offset='int,>=0', length='int,>=1')
    def search(self, data, offset, length, additional_params=None):
        # todo merge paging with additional_params
        res = self.es.get('%s/image/_search' % (self.indexname), data=data, params={'from': offset, 'size': length})
        if not res.has_key('hits') or res['hits']['total'] == 0:
            return [], 0
        return self.map_search_results(res), int(res['hits']['total'])

    def get(self, store_key):
        check_store_key(store_key)
        res = self.es.get('%s/image/%s' % (self.indexname, store_key))
        if not res['exists']:
            return None
        return dict(store_key=store_key, **res['_source'])

    #@contract(upload_group='str[>0]')
    def create(self, upload_group, store_key, original_filename=None, **properties):
        check_store_key(store_key)
        self.es.put("%s/image/%s" % (self.indexname, store_key),
                    data=dict(original_filename=original_filename,
                              upload_group=upload_group,
                              created_at=datetime.now(tz.gettz()),
                              **properties))

    def delete(self, store_key):
        check_store_key(store_key)
        self.es.delete("%s/image/%s" % (self.indexname, store_key))
