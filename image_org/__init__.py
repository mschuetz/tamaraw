from flask import Flask, render_template, request, redirect, url_for, abort, session, Response, send_file, g, jsonify
import boto, MySQLdb, os, json

with open(os.environ['HOME'] + '/.image_org.conf') as f:
    config = json.load(f)

s3 = boto.connect_s3(**config['s3']['credentials']).get_bucket(config['s3']['bucket'])

app = Flask('image_org')
app.config['SECRET_KEY'] = 'ohchohyaqu3imiew4oLahgh4oMa3Shae'
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
