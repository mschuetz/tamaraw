from flask import Flask, render_template, request, redirect, url_for, abort, session, Response, send_file, g, jsonify
import os, json, dao, re
from werkzeug.utils import secure_filename
from flask.helpers import flash
from image_org.store import S3Store, LocalStore
from datetime import datetime
from dateutil import tz

if os.environ.has_key('IMAGE_DB_CONFIG'):
    config_file = os.environ['IMAGE_DB_CONFIG']
else:
    config_file = os.environ['HOME'] + '/.image_org.conf'
 
with open(config_file) as f:
    config = json.load(f)

if config['store'] == 's3':
    store = S3Store(config['s3']['credentials'], config['s3']['bucket'], 'images_')
elif config['store'] == 'local':
    store = LocalStore(config['localstore']['basepath'])
else:
    raise Exception('no store backend configured, must be s3 or local')

dao_conf = [config['elasticsearch']['rawes'], config['elasticsearch']['indexname']]
image_dao = dao.ImageDao(*dao_conf)
config_dao = dao.ConfigDao(*dao_conf)

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask('image_org')
app.config['SECRET_KEY'] = 'ohchohyaqu3imiew4oLahgh4oMa3Shae'

def linkify_image(image):
    return dict(href=url_for('get_image', store_key=image['store_key']), **image)

@app.route('/images/<store_key>')
def api_get_image(store_key):
    return jsonify(linkify_image(image_dao.get(store_key)))

@app.route('/images/')
@app.route('/images')
def api_list_images():
    offset = int(request.args.get('offset') or 0)
    length = int(request.args.get('length') or 100)
    images, total = image_dao.search({'query': dao.range_query('created_at', datetime.fromtimestamp(0, tz.gettz()), datetime.now(tz.gettz())),
                                     'sort': {'created_at': {'order': 'desc'}}},
                                    offset, length)

    return jsonify(total=total, images=[linkify_image(image) for image in images])

@app.route('/images/<store_key>/file')
def get_image(store_key):
    try:
        x = int(request.args.get('x'))
        y = int(request.args.get('y'))
        return store.deliver_image(store_key, (x, y))
    except Exception, e:
        # app.logger.exception('get_image')
        return store.deliver_image(store_key)

# the accompanying website
@app.route('/site/recent/', defaults={'offset': 0})
@app.route('/site/recent/<int:offset>')
def recent_images(offset):
    page_size = request.args.get('page_size') or 8
    images, total = image_dao.search({'query': dao.range_query('created_at', datetime.fromtimestamp(0, tz.gettz()), datetime.now(tz.gettz())),
                                         'sort': {'created_at': {'order': 'desc'}}},
                                        offset, page_size)
    has_more = total > (offset + page_size)
    return render_image_list(images, 'recent.html', page_size, offset, has_more)

@app.route('/site/upload_group/<upload_group>/', defaults={'offset': 0})
@app.route('/site/upload_group/<upload_group>/<int:offset>')
def upload_group(upload_group, offset):
    page_size = request.args.get('page_size') or 8
    images, total = image_dao.search({'query': {'match': {'upload_group': upload_group}},
                                         'sort': {'created_at': {'order': 'desc'}}},
                                        offset, page_size)
    has_more = total > (offset + page_size)
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
    return render_template(template_name, **params)

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
                app.logger.info('saved file under store_key %s', store_key)
                try:
                    image_dao.create(upload_group, store_key, file.filename)
                except Exception as e:
                    app.logger.exception('caught exception while persisting new image to database, removing from store')
                    store.remove(store_key)
                    raise e
                app.logger.info('image with store_key %s persisted in database', store_key)
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

@app.route('/site/image/<store_key>')
def image_page(store_key):
    try:
        image = image_dao.get(store_key)
        if image == None:
            abort(404)
        prop_config = config_dao.get_property_config()
        view_props = create_view_props(image, prop_config, set('prop_title'))
        return render_template('image.html', image=image, view_props=view_props)
    except dao.InvalidStoreKey:
        app.logger.warning('invalid store_key %s', repr(store_key))
        abort(400)

@app.route('/site/image/<store_key>/edit', methods=['POST'])
def save_image(store_key):
    image = image_dao.get(store_key)
    prop_config = config_dao.get_property_config()
    for prop in prop_config:
        key = prop['key']
        image[key] = request.form[key]
    image_dao.put(store_key, image)
    return redirect(url_for('image_page', store_key=store_key))

from contracts import contract

def create_view_props(image, prop_config, exclude=set([])):
    view_props = []
    language = config['language']
    for prop in prop_config:
        if prop['key'] in exclude:
            next
        this_view_prop = {'key': prop['key'], 'human_name': prop['human_' + language]}
        view_props.append(this_view_prop)
        if image.has_key(prop['key']):
            this_view_prop['value'] = image[prop['key']]
            this_view_prop['placeholder'] = ''
        else:
            this_view_prop['value'] = ''
            this_view_prop['placeholder'] = this_view_prop['human_name']
    return view_props

@app.route('/site/image/<store_key>/edit')
def edit_image(store_key):
    image = image_dao.get(store_key)
    if image == None:
        abort(404)
    prop_config = config_dao.get_property_config()
    view_props = create_view_props(image, prop_config)
    return render_template('edit.html', view_props=view_props, store_key=store_key)

@app.route('/site/search')
def quick_search():
    query = request.args.get('query')
    if query == None:
        abort(400)
    prop_config = config_dao.get_property_config()
    fields = [prop['key'] for prop in prop_config]
    images, total = image_dao.search({'query': {'multi_match': {'query': query, 'fields': fields}}}, 0, 10)
    print images
    return render_template('search.html', images=images, next_offset=0, prev_offset=0)

@app.route('/site/<template>/<path:more>')
@app.route('/site/<template>/')
@app.route('/site/<template>')
def site(template, more=None):
    return render_template(template + '.html')

@app.route('/')
def start():
    return site('start')
