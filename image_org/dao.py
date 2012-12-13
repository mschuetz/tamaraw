import rawes
from datetime import datetime
from dateutil import tz

def range_query(field, _from, to):
    return {'range': {field: {'from': _from, 'to': to}}}

class ImageDao:
    def __init__(self, rawes_params, indexname):
        self.es = rawes.Elastic(**rawes_params)
        self.indexname = indexname
        
    def map_search_results(self, rawes_result):
        return [dict(store_key=hit['_id'], **hit['_source']) for hit in rawes_result['hits']['hits']]

    def search(self, data, offset, length, additional_params=None):
        # todo merge paging with additional_params
        res = self.es.get('%s/image/_search' % (self.indexname), data=data, params={'from': offset, 'size': length})
        return self.map_search_results(res), int(res['hits']['total']) > (offset + length)
    
    def get(self, store_key):
        res = self.es.get('%s/image/%s' % (self.indexname, store_key))
        if not res['exists']:
            return None
        return dict(store_key=store_key, **res['_source'])
    
    def create(self, upload_group, store_key, original_filename):
        self.es.put("%s/image/%s" % (self.indexname, store_key),
                    data={'original_filename': original_filename,
                          'upload_group': upload_group,
                          'created_at': datetime.now(tz.gettz())})

