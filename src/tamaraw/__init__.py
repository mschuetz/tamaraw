# encoding: utf-8
from flask import Flask, render_template, request, redirect, url_for, abort, session, jsonify
import urlparse
import urllib
from flask.helpers import flash
from datetime import datetime
from dateutil import tz

import dao
from store import S3Store, LocalStore, SimpleS3Store
from util import InvalidStoreKey
from util import load_config

config = load_config()

if config['store'] == 's3':
    store = S3Store(config['s3']['credentials'], config['s3']['bucket'], 'images_')
elif config['store'] == 'simples3':
    store = SimpleS3Store(config['simples3']['credentials'],
                          config['simples3']['bucket'],
                          config['simples3']['baseurl'],
                          'images_')
elif config['store'] == 'local':
    store = LocalStore(config['localstore']['basepath'])
else:
    raise Exception('no store backend configured, must be s3 or local')

dao_conf = [config['elasticsearch']['rawes'], config['elasticsearch']['indexname']]
config_dao = dao.ConfigDao(*dao_conf)
comment_dao = dao.CommentDao(*dao_conf)
image_dao = dao.ImageDao(*dao_conf)
user_dao = dao.UserDao(*dao_conf)

ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask('tamaraw')
app.config['SECRET_KEY'] = str(config['session_secret'])

def linkify_image(image):
    return dict(href=url_for('get_image', store_key=image['store_key']), **image)

# permissions concept:
# mutating methods are disallowed for unauthenticated users on all resources except:
#     * /public/*
#     * /login & /logout
# GET requests are allowed everywhere except if the resource starts with /private
@app.before_request
def only_get_unless_logged_in():
    if 'username' in session:
        return
    url = urlparse.urlsplit(request.url)
    if url.path in (url_for('login'), url_for('logout')) or url.path.startswith('/public'):
        return
    if not url.path.startswith('/private') and request.method == 'GET':
        return
    abort(403)

@app.route('/api/images/<store_key>')
def api_get_image(store_key):
    return jsonify(linkify_image(image_dao.get(store_key)))

@app.route('/api/images/')
@app.route('/api/images')
def api_list_images():
    offset = int(request.args.get('offset') or 0)
    length = int(request.args.get('length') or 100)
    images, total = image_dao.search({'query': dao.range_query('created_at', datetime.fromtimestamp(0, tz.gettz()), datetime.now(tz.gettz())),
                                     'sort': {'created_at': {'order': 'desc'}}},
                                    offset, length)

    return jsonify(total=total, images=[linkify_image(image) for image in images])

@app.route('/files/<store_key>')
def get_image(store_key):
    try:
        x = int(request.args.get('x'))
        y = int(request.args.get('y'))
        return store.deliver_image(store_key, (x, y))
    except Exception:
        # app.logger.exception('get_image')
        return store.deliver_image(store_key)

# the accompanying website
@app.route('/recent/o<int:offset>')
@app.route('/recent/', defaults={'offset': 0})
def recent_images(offset):
    session['last_collection'] = "/recent/%s" % (offset,)
    page_size = request.args.get('page_size') or 8
    images, total = image_dao.search({'query': dao.range_query('created_at', datetime.fromtimestamp(0, tz.gettz()), datetime.now(tz.gettz())),
                                         'sort': {'created_at': {'order': 'desc'}}},
                                        offset, page_size)
    has_more = total > (offset + page_size)
    return render_image_list(images, 'recent.html', page_size, offset, has_more)

@app.route('/upload_group/<upload_group>/', defaults={'offset': 0})
@app.route('/upload_group/<upload_group>/o<int:offset>')
def upload_group(upload_group, offset):
    session['last_collection'] = "/upload_group/%s/%s" % (upload_group, offset)
    page_size = request.args.get('page_size') or 8
    images, total = image_dao.search({'query': {'match': {'upload_group': upload_group}},
                                         'sort': {'created_at': {'order': 'desc'}}},
                                        offset, page_size)
    has_more = total > (offset + page_size)
    return render_image_list(images, 'upload_group.html', int(page_size), offset, has_more)

def render_image_list(images, template_name, page_size, offset, has_more):
    for image in images:
        for key in image:
            if image[key] is None:
                image[key] = ''
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

@app.route('/upload', methods=['GET'])
def upload_page():
    if 'username' not in session:
        flash('you need to be logged in to upload files', 'alert-warning')
    return render_template('upload.html', upload_group=uuid.uuid4())

@app.route('/upload/<upload_group>', methods=['POST'])
def upload_file(upload_group):
    status = 500
    try:
        file = request.files['file']
        if file.filename and allowed_file(file.filename):
            store_key = store.save(file)
            app.logger.info('saved file under store_key %s', store_key)
            try:
                image_dao.create(upload_group, store_key, file.filename)
            except Exception as e:
                app.logger.exception('caught exception while persisting new image to database, removing from store')
                store.delete(store_key)
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

@app.route('/public/image/<store_key>/comment', methods=['POST'])
def comment(store_key):
    comment_dao.save(request.form['name'], request.form['email'], store_key, request.form['text'])
    flash('your comment was submitted to the author', 'alert-success')
    return redirect(url_for('image_page', store_key=store_key))

@app.route('/image/<store_key>')
def image_page(store_key):
    try:
        image = image_dao.get(store_key)
        if image == None:
            abort(404)
        prop_config = config_dao.get_property_config()
        view_props = create_view_props(image, prop_config, set('prop_title'))
        return render_template('image.html', image=image, view_props=view_props)
    except InvalidStoreKey:
        app.logger.warning('invalid store_key %s', repr(store_key))
        abort(400)

@app.route('/image/<store_key>/edit', methods=['POST'])
def save_image(store_key):
    return_to_edit = False
    image = image_dao.get(store_key)
    prop_config = config_dao.get_property_config()
    for prop in prop_config:
        key = prop['key']
        # need to iterate over array elements first because their actual key does not exist in the form
        # so it would collide with l171 where I set a property to None if the form doesn't contain the key/is empty
        if prop['type'] == 'array':
            image[key] = []
            for i in xrange(0, 100):
                arr_key = key + str(i)
                if arr_key in request.form:
                    image[key].append(request.form[arr_key])
        else:
            if key not in request.form or request.form[key] == '':
                image[key] = None
            elif prop['type'] == 'integer':
                try:
                    image[key] = int(request.form[key])
                except ValueError:
                    flash('%s must be of type %s' % (prop['human_' + config['language']], prop['type']), 'alert-error')
                    return_to_edit = True
            else:
                image[key] = request.form[key]
    if return_to_edit:
        view_props = create_view_props(image, prop_config)
        return render_template('edit.html', view_props=view_props, store_key=store_key)
    else:
        image_dao.put(store_key, image)
        return redirect(url_for('image_page', store_key=store_key))

def create_view_props(image, prop_config, exclude=set([])):
    view_props = []
    language = config['language']
    for prop in prop_config:
        if prop['key'] in exclude:
            next
        this_view_prop = {'key': prop['key'], 'human_name': prop['human_' + language], 'type': prop['type']}
        view_props.append(this_view_prop)
        if image.has_key(prop['key']):
            this_view_prop['value'] = image[prop['key']] or ''
            this_view_prop['placeholder'] = ''
        else:
            if prop['type'] == 'array':
                this_view_prop['value'] = []
            else:
                this_view_prop['value'] = ''
            this_view_prop['placeholder'] = this_view_prop['human_name']
    return view_props

@app.route('/image/<store_key>/edit')
def edit_image(store_key):
    image = image_dao.get(store_key)
    if image == None:
        abort(404)
    prop_config = config_dao.get_property_config()
    view_props = create_view_props(image, prop_config)
    return render_template('edit.html', view_props=view_props, store_key=store_key)

@app.route('/search/', defaults={'offset': 0})
@app.route('/search/o<int:offset>')
def quick_search(offset):
    page_size = request.args.get('page_size') or 8
    query = request.args.get('query')
    if query == None:
        abort(400)
    prop_config = config_dao.get_property_config()
    fields = [prop['key'] for prop in prop_config]
    images, total = image_dao.search({'query': {'multi_match': {'query': query, 'fields': fields}}}, offset, page_size)
    has_more = total > (offset + page_size)
    return render_image_list(images, 'search.html', page_size, offset, has_more)

@app.route('/browse/<key>/<value>/', defaults={'offset': 0})
@app.route('/browse/<key>/<value>/o<int:offset>')
def browse(key, value, offset):
    page_size = request.args.get('page_size') or 8
    # workaround for flask bug?
    if '%' in value:
        value = urllib.unquote(urllib.unquote(value))
        return redirect(url_for('browse', key=key, value=value, offset=offset))
    images, total = image_dao.search({'query': {'match': {key: {'query': value, 'operator': 'and'}}}}, offset, page_size)
    has_more = total > (offset + page_size)
    return render_image_list(images, 'search.html', page_size, offset, has_more)

@app.route('/image/<store_key>/delete', methods=['POST'])
def delete_image(store_key):
    try:
        image_dao.delete(store_key)
        store.delete(store_key)
        flash('successfully deleted file', 'alert-success')
        app.logger.info('deleted image with store key %s', store_key)
    except InvalidStoreKey:
        app.logger.warning("invalid store key %s" , repr(store_key))
        abort(400)
    except OSError:
        # if this file causes persistent errors, it should be ok to let the user remove it
        app.logger.exception("caught exception while removing file")
        flash('ignorable error while deleting file', 'alert-warning')
    image_dao.refresh_indices()
    if 'last_collection' in session:
        return redirect(session['last_collection'])
    else:
        return redirect(url_for('recent_images', offset=0))

@app.route('/<template>/<path:more>')
@app.route('/<template>/')
@app.route('/<template>')
def site(template, more=None):
    return render_template(template + '.html')

@app.route('/logout', methods=['POST'])
def logout():
    if 'username' in session:
        del session['username']
    flash("logout succesful", 'alert-success')
    return redirect(request.referrer)

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    if user_dao.check_credentials(username, request.form['password']):
        app.logger.info('succesful login username=%s', username)
        session['username'] = username
        flash("login succesful", 'alert-success')
    else:
        app.logger.warn('authentication error, username=%s', username)
        flash("wrong username or password", 'alert-error')
    return redirect(request.referrer)

@app.route('/')
def start():
    return site('start')
