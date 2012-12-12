from flask import Flask, render_template, request, redirect, url_for, abort, session, Response, send_file, g, jsonify
import os, json
from werkzeug.utils import secure_filename
from flask.helpers import flash
from image_org.store import S3Store, LocalStore
import rawes
from datetime import datetime
from dateutil import tz

with open(os.environ['HOME'] + '/.image_org.conf') as f:
    config = json.load(f)

if config['store'] == 's3':
    store = S3Store(config['s3']['credentials'], config['s3']['bucket'], 'images_')
elif config['store'] == 'local':
    store = LocalStore(config['localstore']['basepath'])
else:
    raise Exception('no store backend configured, must be s3 or local')

es = rawes.Elastic(**config['elasticsearch']['rawes'])
es_index = config['elasticsearch']['indexname']

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask('image_org')
app.config['SECRET_KEY'] = 'ohchohyaqu3imiew4oLahgh4oMa3Shae'

@app.teardown_request
def teardown_request(exception):
    if hasattr(g, 'cursor'):
        g.cursor.close()

@app.route('/images/<store_key>/file')
def get_image(store_key):
    try:
        x = int(request.args.get('x'))
        y = int(request.args.get('y'))
        return store.deliver_image(store_key, (x, y))
    except Exception, e:
        # app.logger.exception('get_image')
        return store.deliver_image(store_key)

def map_search_results(rawes_result):
    return [dict(store_key=hit['_id'], **hit['_source']) for hit in rawes_result['hits']['hits']]

def search_images(data, offset, length, additional_params=None):
    # todo merge paging with additional_params
    res = es.get('%s/image/_search' % (es_index), data=data, params={'from': offset, 'size': length})
    return map_search_results(res), int(res['hits']['total']) > (offset + length)

def range_query(field, _from, to):
    return {'range': {field: {'from': _from, 'to': to}}}

# the accompanying website
@app.route('/site/recent/', defaults={'offset': 0})
@app.route('/site/recent/<int:offset>')
def recent_images(offset):
    page_size = request.args.get('page_size') or 8
    images, has_more = search_images({'query': range_query('created_at', datetime.fromtimestamp(0, tz.gettz()), datetime.now(tz.gettz())),
                                      'sort': {'created_at': {'order': 'desc'}}},
                                     offset, page_size)
    return render_image_list(images, 'recent.html', page_size, offset, has_more)

@app.route('/site/upload_group/<upload_group>/', defaults={'offset': 0})
@app.route('/site/upload_group/<upload_group>/<int:offset>')
def upload_group(upload_group, offset):
    page_size = request.args.get('page_size') or 8
    images, has_more = search_images({'query': {'match': {'upload_group': upload_group}},
                                      'sort': {'created_at': {'order': 'desc'}}},
                                     offset, page_size)
    return render_image_list(images, 'upload_group.html', int(page_size), offset, has_more)

def render_image_list(images, template_name, page_size, offset, has_more):
    params = {'images': images, 'offset': offset}
    if has_more:
        params['next_offset'] = offset + page_size
    if offset > 0:
        prev_offset = offset - page_size
        if prev_offset > 0:
            params['prev_offset'] = prev_offset
        else: 
            params['prev_offset'] = 0
    return render_template('recent.html', **params)
    

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

import uuid, sys

@app.route('/site/upload', defaults={'upload_group': None}, methods=['GET'])
@app.route('/site/upload/<upload_group>', methods=['POST'])
def upload_file(upload_group):
    status = 500
    if request.method == 'POST':
        try:
            file = request.files['file']
            if file.filename and allowed_file(file.filename):
                store_key = store.save(file)
                #g.cursor.execute('insert into images (store_key, upload_group) values (%s, %s)', (store_key, upload_group))
                #g.db.commit()
                es.put("%s/image/%s" % (es_index, store_key), data={
                        'original_filename': file.filename,
                        "upload_group": upload_group,
                        "created_at": datetime.now(tz.gettz())})
                status = 200
                flash('successfully uploaded file', 'alert-success')
            else:
                status = 400
                app.logger.warning('invalid filename: %s', repr(file.filename))
                flash('invalid file', 'alert-error')
        except:
            status = 500
            app.logger.exception('error during upload')
            flash('encountered an exception during upload ' + str(sys.exc_info()[0]), 'alert-error')
            
    return render_template('upload.html', upload_group=uuid.uuid4()), status
import re
@app.route('/site/image/<store_key>')
def image_page(store_key):
    if not re.match("^[0-9a-zA-Z_]+$", store_key):
        app.logger.warning('invalid store_key %s', repr(store_key))
        abort(400)
    res = es.get('%s/image/%s' % (es_index, store_key))
    if not res['exists']:
        abort(404)
    image = res['_source']
    image['store_key'] = store_key
    return render_template('image.html', image=image)

@app.route('/site/<template>')
def site(template):
    return render_template(template + '.html')

@app.route('/')
def start():
    return site('start')
