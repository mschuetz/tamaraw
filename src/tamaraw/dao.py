# encoding: utf-8
import rawes, re
from datetime import datetime
from dateutil import tz
from contracts import contract
from util import check_store_key
import dateutil.parser
def range_query(field, _from, to):
    return {'range': {field: {'from': _from, 'to': to}}}

class ConfigDao:

    DEFAULT_PROPS = [
                     {u"key": u"prop_title", u"human_de": u"Kurztitel", u"default": True, u"type": 'string', u"use_for_browse": False},
                     {u"key": u"prop_source", u"human_de": u"Quelle", u"default": True, u"type": 'string', u"use_for_browse": True},
                     {u"key": u"prop_rights", u"human_de": u"Bildrechte", u"default": True, u"type": 'string', u"use_for_browse": True},
                     {u"key": u"prop_master", u"human_de": u"Vorlage", u"default": True, u"type": 'string', u"use_for_browse": True},
                     {u"key": u"prop_description", u"human_de": u"Bildbeschreibung", u"default": True, u"type": 'text', u"use_for_browse": False},
                     {u"key": u"prop_source_description", u"human_de": u"Originalbildunterschrift", u"default": True, u"type": 'text', u"use_for_browse": False},
                     {u"key": u"prop_creation_year", u"human_de": u"Aufnahmejahr", u"default": True, u"type": 'integer', u"use_for_browse": True},
                     {u"key": u"prop_location", u"human_de": u"Aufnahmeort", u"default": True, u"type": 'string', u"use_for_browse": True},
                     {u"key": u"prop_tags", u"human_de": u"Sachbegriffe", u"default": True, u"type": 'array', u"use_for_browse": True}]
    
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
        
    def map_timestamps(self, obj):
        for known_timestamp in ('created_at', 'updated_at'):
            if known_timestamp in obj:
                try:
                    obj[known_timestamp] = dateutil.parser.parse(obj[known_timestamp])
                except:
                    pass
        return obj

    # @contract(rawes_result='dict(unicode: *)', returns='tuple(list, int, (None|dict)')
    @contract(rawes_result='dict(unicode: *)')
    def map_search_results(self, rawes_result):
        if not rawes_result.has_key('hits') or rawes_result['hits']['total'] == 0:
            return [], 0
        hits = [dict(store_key=hit['_id'], **self.map_timestamps(hit['_source'])) for hit in rawes_result['hits']['hits']]
        total = int(rawes_result['hits']['total'])
        if 'facets' not in rawes_result:
            return hits, total
        facets = {}
        for facet_key, facet in rawes_result['facets'].iteritems():
            terms = {}
            for term in facet['terms']:
                terms[term['term']] = term['count']
            facets[facet_key] = terms 
        return hits, total, facets

    @contract(data='dict(str: *)', offset='int,>=0', page_size='int,>=1')
    def search(self, data, offset, page_size, additional_params=None):
        # todo merge paging with additional_params
        res = self.es.get('%s/image/_search' % (self.indexname), data=data, params={'from': offset, 'size': page_size})
        return self.map_search_results(res)
    
    @contract(offset='int,>=0', page_size='int,>=1')
    def upload_group_by_creation(self, upload_group, offset, page_size):
        return self.search({'query': {'match': {'upload_group': upload_group}},
                            'sort': {'created_at': {'order': 'desc'}}},
                            offset, page_size)
    
    @contract(offset='int,>=0', page_size='int,>=1')
    def recent(self, offset, page_size):
        return self.search({'query': range_query('created_at', datetime.fromtimestamp(0, tz.gettz()), datetime.now(tz.gettz())),
                            'sort': {'created_at': {'order': 'desc'}}},
                           offset, page_size)

    @contract(offset='int,>=0', page_size='int,>=1')
    def browse(self, key, value, offset, page_size):
        return self.search({'query': {'match': {key: {'query': value, 'operator': 'and'}}}}, offset, page_size)
        
    def get(self, store_key):
        check_store_key(store_key)
        res = self.es.get('%s/image/%s' % (self.indexname, store_key))
        if not res['exists']:
            return None
        return dict(store_key=store_key, **self.map_timestamps(res['_source']))

    # TODO how cam i assure that it's either str or unicode? pycontracts doesn't know basestring
    # @contract(upload_group='str[>0]')
    def create(self, upload_group, store_key, original_filename=None, **properties):
        check_store_key(store_key)
        self.es.put("%s/image/%s" % (self.indexname, store_key),
                    data=dict(original_filename=original_filename,
                              upload_group=upload_group,
                              created_at=datetime.now(tz.gettz()),
                              updated_at=datetime.now(tz.gettz()),
                              **properties))

    def put(self, store_key, image):
        check_store_key(store_key)
        image_without_store_key = dict(**image)
        if image.has_key('store_key'):
            del image_without_store_key['store_key']
        image_without_store_key['updated_at'] = datetime.now(tz.gettz())
        self.es.put("%s/image/%s" % (self.indexname, store_key), data=image_without_store_key)

    def delete(self, store_key):
        check_store_key(store_key)
        self.es.delete("%s/image/%s" % (self.indexname, store_key))

    def refresh_indices(self):
        self.es.post("%s/_refresh" % (self.indexname))

class UserDao:
    import passlib.hash
    def __init__(self, rawes_params, indexname, hash_algo=passlib.hash.pbkdf2_sha256):
        self.es = rawes.Elastic(**rawes_params)
        self.indexname = indexname
        self.hash_algo = hash_algo

    def check_credentials(self, username, password):
        res = self.es.get("%s/user/%s" % (self.indexname, username))
        if not res['exists']:
            return None
        return self.hash_algo.verify(password, res['_source']['hash'])

    def create_user(self, username, password):
        res = self.es.put("%s/user/%s" % (self.indexname, username), data={'hash': self.hash_algo.encrypt(password)})
        if not res['ok']:
            raise Exception(res)

class InvalidCommentId(Exception):
    pass

class CommentDao:
    def __init__(self, rawes_params, indexname):
        self.es = rawes.Elastic(**rawes_params)
        self.indexname = indexname

    @contract(offset='int,>=0', length='int,>=1', returns='tuple(list, int)')
    def get(self, store_key, offset, length):
        check_store_key(store_key)
        return self.search({'match': {'store_key': store_key}}, offset, length)

    @contract(offset='int,>=0', length='int,>=1', returns='tuple(list, int)')
    def get_all(self, offset, length):
        return self.search({'match_all': {}}, offset, length)

    @contract(query='dict(str: *)', offset='int,>=0', length='int,>=1', returns='tuple(list, int)')
    def search(self, query, offset, length):
        res = self.es.get('%s/comment/_search' % (self.indexname),
                          data={'query': query,
                                'sort': {'created_at': {'order': 'desc'}}},
                          params={'from': offset, 'size': length})
        return self.map_search_results(res)

    @contract(rawes_result='dict(unicode: *)')
    def map_search_results(self, rawes_result):
        if not rawes_result.has_key('hits') or rawes_result['hits']['total'] == 0:
            return [], 0
        hits = [dict(_id=hit['_id'], **hit['_source']) for hit in rawes_result['hits']['hits']]
        total = int(rawes_result['hits']['total'])
        return hits, total

    def mark_as_read(self, comment_id):
        if (re.match("[\.\\\/]", comment_id)):
            raise InvalidCommentId
        path = '%s/comment/%s' % (self.indexname, comment_id)
        res = self.es.get(path)
        if not res['exists']:
            None
        comment = res['_source']
        if not comment['read']:
            comment['read'] = True
            self.es.put(path, data=comment)
        return comment

    def save(self, name, email, store_key, text):
        check_store_key(store_key)
        self.es.post("%s/comment/" % (self.indexname,),
                     data=dict(name=name,
                               email=email,
                               store_key=store_key,
                               text=text,
                               created_at=datetime.now(tz.gettz()),
                               read=False))
