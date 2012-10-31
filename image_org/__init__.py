from flask import Flask, render_template, request, redirect, url_for, abort, session, Response, send_file, g, jsonify
import MySQLdb, os, json
from collections import namedtuple
from werkzeug.utils import secure_filename
from flask.helpers import flash
from image_org.store import S3Store, LocalStore

with open(os.environ['HOME'] + '/.image_org.conf') as f:
    config = json.load(f)

#store = S3Store(config['s3']['credentials'], config['s3']['bucket'], 'images_')
store = LocalStore('/tmp')

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask('image_org')
app.config['SECRET_KEY'] = 'ohchohyaqu3imiew4oLahgh4oMa3Shae'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

@app.before_request
def before_request():
    def connect_db():
        g.db = MySQLdb.connect(**config['database'])
        g.cursor = g.db.cursor()
    if hasattr(g, 'db'):
        try:
            g.cursor = g.db.cursor()
            g.cursor.execute('select 1+1')
        except:
            connect_db()
    else:
        connect_db()

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
        #print >>sys.stderr, 'get_image: ex = %s' % e
        return store.deliver_image(store_key)

@app.route('/images/<store_key>', )
def get_properties(store_key):
    def add_rows(cursor, obj):
        for row in g.cursor:
            key, value = row
            obj[key] = value
    
    if g.cursor.execute('select id, created_at from images where store_key=%s', store_key) == 0:
        abort(404)

    image_id, created_at = g.cursor.fetchone()
    
    g.cursor.execute("""select property_types.name, images_text.value from images_text
                        join property_types on property_types.id=images_text.property_type_id
                        where images_text.image_id=%s""", image_id)

    properties = {}
    add_rows(g.cursor, properties)

    g.cursor.execute("""select property_types.name, enum_values.name from images_enums
                        join enum_values on images_enums.enum_value_id=enum_values.id
                        join property_types on property_types.id=enum_values.type_id
                        where images_enums.image_id=%s""", image_id)
    add_rows(g.cursor, properties)
#    return jsonify({store_key: {'created_at': str(created_at), 'href': '/%s/file' % (store_key), 'properties': properties}})
    render_template('image')

class Image:
    def __init__(self, db_id, created_at, store_key):
        self.db_id = db_id
        self.created_at = created_at
        self.store_key = store_key 

def to_image_list(cursor, page_size):
    images = []
    more = False
    for row in cursor:
        if len(images) == page_size:
            more = True
            break
        images.append(Image(row[0], row[1], row[2]))
    return images, more

# the accompanying website
@app.route('/site/recent', defaults={'offset': 0})
@app.route('/site/recent/<int:offset>')
def recent_images(offset):
    page_size = 5
    g.cursor.execute('select id, created_at, store_key from images order by created_at desc limit %s,%s', (offset, page_size + 1))
    images, more = to_image_list(g.cursor, page_size)
    params = {'images': images, 'offset': offset}
    if more:
        params['next_offset'] = offset + page_size
    if offset > 0:
        prev_offset = offset - page_size
        if prev_offset > 0:
            params['prev_offset'] = prev_offset
        else: 
            params['prev_offset'] = 0
    print params
    return render_template('recent.html', **params)

@app.route('/site/upload_group/<upload_group>', defaults={'offset': 0})
@app.route('/site/recent/<upload_group>/<int:offset>')
def upload_group(upload_group, offset):
    page_size = 20
    g.cursor.execute('select id, created_at, store_key from images where upload_group=%s order by created_at desc limit %s,%s', (upload_group, offset, page_size + 1))
    images, more = to_image_list(g.cursor)
    return render_template('upload_group.html', images=images, more=more, page_size=page_size, offset=offset)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

import uuid,sys

@app.route('/site/upload', defaults={'upload_group': None}, methods=['GET'])
@app.route('/site/upload/<upload_group>', methods=['POST'])
def upload_file(upload_group):
    if request.method == 'POST':
        try:
            file = request.files['file']
            if file.filename and allowed_file(file.filename):
                store_key = store.save(file)
                g.cursor.execute('insert into images (store_key, upload_group) values (%s, %s)', (store_key, upload_group))
                g.db.commit()
                flash('successfully uploaded file', 'alert-success')
            else:
                flash('invalid file', 'alert-error')
        except:
            app.logger.exception('error during upload')
            flash('encountered an exception during upload ' + str(sys.exc_info()[0]), 'alert-error')
            
    return render_template('upload.html', upload_group=uuid.uuid4())

@app.route('/site/<template>')
def site(template):
    return render_template(template + '.html')

@app.route('/')
def start():
    return site('start')
