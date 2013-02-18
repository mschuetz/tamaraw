# encoding: utf-8
from flask import Flask, request, redirect, url_for, abort, session, jsonify
from flask import render_template as flask_render_template
import urlparse
import urllib
import mimetypes
import re
from flask.helpers import flash
from datetime import datetime
from dateutil import tz
from jinja2 import TemplateNotFound
from functools import partial 
from contracts import contract

import dao
from storage import LocalStore, SimpleS3Store, FileCache
from util import InvalidStoreKey
from util import load_config

config = load_config()

app = Flask('tamaraw')
app.config['SECRET_KEY'] = str(config['session_secret'])

if config['store'] == 'simples3':
    store = SimpleS3Store(config['simples3']['credentials'],
                          config['simples3']['bucket'],
                          config['simples3']['baseurl'],
                          app.logger,
                          'images_',
                          FileCache(config['cache']['basepath']))
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

def get_git_version():
    import subprocess, os
    # os.chdir(os.path.dirname(__file__))
    # yes, the arguments must be reversed, wtf?
    p = subprocess.Popen(executable='/usr/bin/git', args=['--always', 'describe'], stdout=subprocess.PIPE)
    version, _ = p.communicate()
    return version.replace("\n", '')

VERSION = get_git_version()

def render_template(name, **kwargs):
    return flask_render_template(name, app_version=VERSION, **kwargs)

@app.template_filter('filter')
def template_filter(values, filter=None):
    res = []
    for val in values:
        if val != filter:
            res.append(val)
    return res

@app.template_filter('date_format')
def template_date_format(value, format='%d.%m.%Y'):
    return value.strftime(format)

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

@app.route('/files/<store_key>', defaults={'x':None, 'y':None})
@app.route('/files/<store_key>_<int:x>x<int:y>')
def get_image(store_key, x, y):
    if x and y:
        return store.deliver_image(store_key, (x, y))
    else:
        return store.deliver_image(store_key)

# the accompanying website
@app.route('/recent/o<int:offset>')
@app.route('/recent/', defaults={'offset': 0})
def recent_images(offset):
    session['last_collection'] = url_for('recent_images', offset=offset)
    page_size = get_page_size()
    images, total = image_dao.recent(offset, page_size)
    return render_image_list(images, 'recent.html', partial(url_for, 'recent_images'), offset, page_size, total,
                             additional_params={'query_name': 'recent_images'})

@app.route('/upload_group/<upload_group>/', defaults={'offset': 0})
@app.route('/upload_group/<upload_group>/o<int:offset>')
def upload_group(upload_group, offset):
    session['last_collection'] = url_for('upload_group', upload_group=upload_group, offset=offset)
    page_size = get_page_size()
    images, total = image_dao.upload_group_by_creation(upload_group, offset, page_size)
    return render_image_list(images, 'upload_group.html', partial(url_for, 'upload_group', upload_group=upload_group),
                             offset, page_size, total, additional_params={'query_name': 'upload_group:%s' % (upload_group,)})

def get_page_size(default=8):
    page_size = request.args.get('page_size') or default
    return int(page_size)

def render_image_list(images, template_name, url_for_func, offset, page_size, total, additional_params={}):
    for image in images:
        for key in image:
            if image[key] is None:
                image[key] = ''
    params = dict(images=images, **additional_params)
    add_pagination_params(params, url_for_func, offset, page_size, total)
    return render_template(template_name, **params)

def add_pagination_params(params, url_for_func, offset, page_size, total):
    params['offset'] = offset
    params['page_size'] = page_size
    params['total'] = total
    if total > (offset + page_size):
        params['next_offset'] = url_for_func(offset=offset + page_size)
    if offset > 0:
        prev_offset = offset - page_size
        if prev_offset > 0:
            params['prev_offset'] = url_for_func(offset=prev_offset)
        else: 
            params['prev_offset'] = url_for_func(offset=0)
    return params
    
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
            # we don't always receive a mimetype via file.content_type, so derive it from the extension 
            mimetype, _ = mimetypes.guess_type(file.filename) or 'application/octet-stream'
            store_key = store.save(file, mimetype=mimetype)
            app.logger.info('saved file under store_key %s with mimetype %s', store_key, mimetype)
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
    result_set = request.args.get('r')
    if result_set:
        return image_page_in_result(store_key, result_set, int(request.args.get('o')))
    else:
        try:
            image = image_dao.get(store_key)
            if image == None:
                abort(404)
            prop_config = config_dao.get_property_config()
            view_props = create_view_props(image, prop_config, set(['prop_title']))
            return render_template('image.html', image=image, view_props=view_props)
        except InvalidStoreKey:
            app.logger.warning('invalid store_key %s', repr(store_key))
            abort(400)

def image_page_in_result(store_key, result_set, offset):
    prev_offset = offset - 1
    is_first = prev_offset == -1
    start_offset = max(prev_offset, 0)
    if result_set == 'recent_images':
        images, total = image_dao.recent(start_offset, 3)
        result_set_title = 'Neue Bilder'
    elif result_set.startswith('upload_group:'):
        _, upload_group = result_set.split(':')
        result_set_title = 'Uploadgruppe ' + upload_group
        images, total = image_dao.upload_group_by_creation(upload_group, start_offset, 3)
    elif result_set.startswith('search:'):
        query = result_set.replace('search:', '')
        result_set_title = 'Volltextsuche: ' + query
        fields = assemble_full_text_fields(query)
        images, total = image_dao.search({'query': {'multi_match': {'query': query, 'fields': fields}}}, start_offset, 3)
    elif result_set.startswith('browse:'):
        tmp = result_set.replace('browse:', '')
        key = tmp[:tmp.index(':')]
        value = tmp[tmp.index(':') + 1:]
        result_set_title = human_name(key) + ': ' + value
        images, total = image_dao.browse(key, value, start_offset, 3)
    else:
        # unknown result set
        return redirect(url_for('image_page', store_key=store_key))

    image = images[int(not is_first)]
    if image['store_key'] != store_key:
        # result set has changed e.g. new uploads or edits changed the order
        flash(u"Das Suchergebnis sich während der Navigation geändert (z.B. durch Hinzufügen neuer Bilder oder durch " + 
              u"Änderung einer Bildbeschreibung etc.). Die Navigation innerhalb des Suchergebnisses kann daher nicht "
              u"fortgesetzt werden. Bitte starten Sie die Suche erneut.", 'alert-warning')
        return redirect(url_for('image_page', store_key=store_key))

    pagination_params = dict(offset=offset, total=total, page_size=1)
    is_last = offset + 1 >= total
    if not is_last:
        pagination_params['next_offset'] = url_for('image_page', store_key=images[1 + int(not is_first)]['store_key'],
                                                   r=result_set, o=offset + 1)
    if not is_first:
        pagination_params['prev_offset'] = url_for('image_page', store_key=images[0]['store_key'], r=result_set, o=offset - 1)
    prop_config = config_dao.get_property_config()
    view_props = create_view_props(image, prop_config, set(['prop_title']))
    return render_template('image.html', image=image, view_props=view_props,
                           in_result_set=True, result_set_title=result_set_title, **pagination_params)

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
                    image[key].append(request.form[arr_key].strip())
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
                image[key] = request.form[key].strip()
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
            continue
        this_view_prop = dict(human_name=prop['human_' + language], **prop)
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

def assemble_full_text_fields(query):
    prop_config = config_dao.get_property_config()
    query_is_number = True
    try:
        int(query)
    except ValueError:
        query_is_number = False

    fields = []        
    for prop in prop_config:
        if query_is_number or prop['type'] != 'integer': 
            fields.append(prop['key'])
    return fields

@app.route('/search/', defaults={'offset': 0})
@app.route('/search/o<int:offset>')
def quick_search(offset):
    page_size = get_page_size()
    query = request.args.get('query')
    if query == None:
        abort(400)
    fields = assemble_full_text_fields(query)
    images, total = image_dao.search({'query': {'multi_match': {'query': query, 'fields': fields}}}, offset, page_size)
    return render_image_list(images, 'search.html', partial(url_for, 'quick_search', query=query),
                             offset, page_size, total, {'search_title': 'Volltextsuche: ' + query,
                                                        'query_name': 'search:' + query})

def human_name(property_key):
    for prop_config in config_dao.get_property_config():
        if prop_config['key'] == property_key:
            return prop_config['human_' + config['language']]
    raise ValueError('not a valid property name')

@contract(returns="list(dict)")
def get_categories():
    props = config_dao.get_property_config()
    return [dict(key=prop['key'], human_name=prop['human_' + config['language']])
            for prop in props if prop['use_for_browse']]

@app.route('/browse/')
def browse_overview():
    return render_template('browse_overview.html', categories=get_categories())

@app.route('/browse/<key>')
def browse_facets(key):
    current = dict(key=key, human_name=human_name(key))
    facet_request = {}
    for prop in config_dao.get_property_config():
        facet_key = prop['key']
        if facet_key != key:
            facet_request[facet_key] = {'terms': {'field': facet_key}}

    facets = [dict(term=k, count=v) for k, v in image_dao.get_facets(key)[key].iteritems()]
    # raise Exception
    return render_template('browse_overview.html', categories=get_categories(), current_category=current, facets=facets)

@app.route('/browse/<key>/<value>/', defaults={'offset': 0})
@app.route('/browse/<key>/<value>/o<int:offset>')
def browse(key, value, offset):
    page_size = get_page_size()
    images, total = image_dao.browse(key, value, offset, page_size)
    category_name = human_name(key)
    return render_image_list(images, 'browse.html', partial(url_for, 'browse', key=key, value=value),
                             offset, page_size, total, {'search_title': '%s: %s' % (category_name, value),
                                                        'query_name': 'browse:%s:%s' % (key, value)})

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
    try:
        return render_template(template + '.html')
    except TemplateNotFound:
        abort(404)

@app.route('/public/subscribe', methods=['POST'])
def subscribe():
    comment_dao.save(request.form['name'], request.form['email'], 'subscribe', request.form['comment'])
    flash(u'Vielen Dank %s, wir werden sie über die Fertigstellung der Seite per Email informieren.' % (request.form['name'],),
          'alert-success')
    return redirect(url_for('start'))

@app.route('/private/comment/<comment_id>/mark_as_read', methods=['POST'])
def mark_comment_as_read(comment_id):
    if comment_dao.mark_as_read(comment_id):
        return '', 200
    else:
        abort(404)

@app.route('/private/comments/', defaults={'offset': 0})
@app.route('/private/comments/o<int:offset>')
def comments(offset):
    page_size = get_page_size()
    comments, total = comment_dao.get_all(offset, page_size)
    params = add_pagination_params({'comments': comments}, partial(url_for, 'comments'), offset, page_size, total)
    return render_template('comments.html', **params)
    
@app.route('/logout')
def logout():
    if 'username' in session:
        del session['username']
    flash("logout succesful", 'alert-success')
    return redirect(url_for('start'))

@app.route('/login', methods=['POST'])
def login():
    username = request.form['username']
    if not re.match('[0-9a-zA-Z\.\-_]', username):
        flash("wrong invalid characters in username", 'alert-error')
    elif user_dao.check_credentials(username, request.form['password']):
        app.logger.info('succesful login username=%s', username)
        session['username'] = username
        flash("login succesful", 'alert-success')
    else:
        app.logger.warn('authentication error, username=%s', username)
        flash("wrong username or password", 'alert-error')
    return redirect(request.referrer)

@app.route('/')
def start():
    images, _ = image_dao.search({'query':{'match_all': {}}}, 0, 5)
    return render_template('start.html', demo_images=images)
