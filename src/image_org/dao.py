import rawes, re
from datetime import datetime
from dateutil import tz
from contracts import contract
from util import check_store_key

def range_query(field, _from, to):
    return {'range': {field: {'from': _from, 'to': to}}}

class ConfigDao:
    DEFAULT_PROPS = [
                     {u"key": u"prop_title", u"human_de": u"Kurztitel", u"default": True},
                     {u"key": u"prop_source", u"human_de": u"Quelle", u"default": True},
                     {u"key": u"prop_master", u"human_de": u"Vorlage", u"default": True},
                     {u"key": u"prop_description", u"human_de": u"Bildbeschreibung", u"default": True},
                     {u"key": u"prop_source_description", u"human_de": u"Originalbildunterschrift", u"default": True},
                     {u"key": u"prop_creation_year", u"human_de": u"Aufnahmejahr", u"default": True},
                     {u"key": u"prop_location", u"human_de": u"Aufnahmeort", u"default": True},
                     {u"key": u"prop_tags", u"human_de": u"Sachbegriffe", u"default": True}]

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
        self.update_property_config(ConfigDao.DEFAULT_PROPS)
    
    @contract(config='list')
    def update_property_config(self, config):
        self.es.put(self.config_path(), data={'obj': config})
    
    @contract(returns='list')
    def get_property_config(self):
        if self.property_config != None:
            return self.property_config
        res = self.es.get(self.config_path())
        if not res.has_key('exists') or not res['exists']:
            self.import_default_props()
            return ConfigDao.DEFAULT_PROPS
        else:
            return res['_source']['obj']

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

    # TODO how cam i assure that it's either str or unicode? pycontracts doesn't know basestring
    # @contract(upload_group='str[>0]')
    def create(self, upload_group, store_key, original_filename=None, **properties):
        check_store_key(store_key)
        self.es.put("%s/image/%s" % (self.indexname, store_key),
                    data=dict(original_filename=original_filename,
                              upload_group=upload_group,
                              created_at=datetime.now(tz.gettz()),
                              **properties))

    def put(self, store_key, image):
        check_store_key(store_key)
        image_without_store_key = dict(**image)
        if image.has_key('store_key'):
            del image_without_store_key['store_key']
        self.es.put("%s/image/%s" % (self.indexname, store_key), data=image_without_store_key)

    def delete(self, store_key):
        check_store_key(store_key)
        self.es.delete("%s/image/%s" % (self.indexname, store_key))
