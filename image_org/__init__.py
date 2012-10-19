from flask import Flask, render_template, request, redirect, url_for, abort, session, Response, send_file, g, jsonify
import boto, MySQLdb, os, json
from collections import namedtuple
from werkzeug.utils import secure_filename
from flask.helpers import flash

with open(os.environ['HOME'] + '/.image_org.conf') as f:
    config = json.load(f)

s3 = boto.connect_s3(**config['s3']['credentials']).get_bucket(config['s3']['bucket'])

UPLOAD_FOLDER = '/tmp'
ALLOWED_EXTENSIONS = set(['png', 'jpg', 'jpeg', 'gif'])

app = Flask('image_org')
app.config['SECRET_KEY'] = 'ohchohyaqu3imiew4oLahgh4oMa3Shae'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
s3_prefix = config['s3']['prefix']

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

@app.route('/images/<s3_key>/file', defaults = {'size': 'original'})
@app.route('/images/<s3_key>/file/<size>')
def get_image(s3_key, size):
    key = s3.get_key(s3_prefix + s3_key)
    if key:
        url = key.generate_url(3600)
        return redirect(url, 307)
    else:
        abort(404)

@app.route('/images/<s3_key>')
def get_properties(s3_key):
    def add_rows(cursor, obj):
        for row in g.cursor:
            key, value = row
            obj[key] = value
    
    if g.cursor.execute('select id, created_at from images where s3_key=%s', s3_key) == 0:
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
    
    return jsonify({s3_key: {'created_at': str(created_at), 'href': '/%s/file' % (s3_key), 'properties': properties}})

#Image = namedtuple('id', 'created_at', 's3_key')

class Image:
    def __init__(self, db_id, created_at, s3_key):
        self.db_id = db_id
        self.created_at = created_at
        self.s3_key = s3_key 

# the accompanying website
@app.route('/site/recent', defaults={'offset': 0})
@app.route('/site/recent/<int:offset>')
def recent_images(offset):
    page_size = 20
    g.cursor.execute('select id, created_at, s3_key from images order by created_at desc limit %s,%s', (offset, page_size + 1))
    images = []
    more = False
    for row in g.cursor:
        if len(images) == 20:
            more = True
            break
        images.append(Image(row[0], row[1], row[2]))
    
    return render_template('recent.html', images=images, more=more, page_size=page_size, offset=offset)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1] in ALLOWED_EXTENSIONS

import uuid,sys
           
@app.route('/site/upload', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        try:
            file = request.files['file']
            if file.filename and allowed_file(file.filename):
                s3_key = str(uuid.uuid4())
                key = s3.new_key(s3_prefix + s3_key)
                key.set_contents_from_file(file)
                
                g.cursor.execute('insert into images (s3_key) values (%s)', (s3_key))
                g.db.commit()
                flash('successfully uploaded file', 'alert-success')
            else:
                flash('invalid file', 'alert-error')
        except:
            app.logger.exception('error during upload')
            flash('encountered an exception during upload ' + str(sys.exc_info()[0]), 'alert-error')
            
    return render_template('upload.html')

@app.route('/site/<template>')
def site(template):
    return render_template(template + '.html')

@app.route('/')
def start():
    return site('start')
