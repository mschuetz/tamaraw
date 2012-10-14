from flask import Flask, render_template, request, redirect, url_for, abort, session, Response, send_file, g, jsonify
import boto, MySQLdb, os, json

with open(os.environ['HOME'] + '/.image_org.conf') as f:
    config = json.load(f)

s3 = boto.connect_s3().get_bucket(config['s3']['bucket'])

app = Flask('picturedb')
app.config['SECRET_KEY'] = 'ohchohyaqu3imiew4oLahgh4oMa3Shae'
s3_prefix = config['s3']['prefix']

def connect_db():
    g.db = MySQLdb.connect(**config['database'])
    g.cursor = g.db.cursor()

@app.before_request
def before_request():
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

@app.route('/<img_id>/file')
def get_image_default(img_id):
    return get_image(img_id, 'original')

@app.route('/<img_id>/file/<size>')
def get_image(img_id, size):
    key = s3.get_key(s3_prefix + img_id)
    if key:
        url = key.generate_url(3600)
        return redirect(url, 307)
    else:
        abort(404)

@app.route('/<s3_key>')
def get_properties(s3_key):
    def add_rows(cursor, obj):
        for row in g.cursor:
            key, value = row
            obj[key] = value
    
    properties = {}
    
    g.cursor.execute("""select property_types.name, images_text.value from images
                        join images_text on images.id=images_text.image_id
                        join property_types on property_types.id=images_text.property_type_id
                        where images.s3_key=%s""", s3_key)
    add_rows(g.cursor, properties)

    g.cursor.execute("""select property_types.name, enum_values.name from images
                        join images_enums on images.id=images_enums.image_id
                        join enum_values on images_enums.enum_value_id=enum_values.id
                        join property_types on property_types.id=enum_values.type_id
                        where images.s3_key=%s""", s3_key)
    add_rows(g.cursor, properties)
    
    return jsonify({s3_key: {'href': '/%s/file' % (s3_key), 'properties': properties}})
