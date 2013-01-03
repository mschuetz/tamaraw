# encoding: utf-8
import random, os, magic, Image, base64, struct, boto, time
from flask import abort, redirect
from flask.helpers import send_file
import tempfile
from util import check_store_key

def unique_id():
    return base64.urlsafe_b64encode(struct.pack('fHH', time.time(), os.getpid() % 65536, random.randint(0, 65535))).replace('=', '_')

# http://united-coders.com/christian-harms/image-resizing-tips-every-coder-should-know/
def resize(img, box, fit, out, quality=75):
    '''Downsample the image.
    @param img: Image -  an Image-object
    @param box: tuple(x, y) - the bounding box of the result image
    @param fix: boolean - crop the image to fill the box
    @param out: file-like-object - save the image into the output stream
    '''
    # preresize image with factor 2, 4, 8 and fast algorithm
    factor = 1
    while img.size[0] / factor > 2 * box[0] and img.size[1] * 2 / factor > 2 * box[1]:
        factor *= 2
    if factor > 1:
        img.thumbnail((img.size[0] / factor, img.size[1] / factor), Image.NEAREST)

    # calculate the cropping box and get the cropped part
    if fit:
        x1 = y1 = 0
        x2, y2 = img.size
        wRatio = 1.0 * x2 / box[0]
        hRatio = 1.0 * y2 / box[1]
        if hRatio > wRatio:
            y1 = int(y2 / 2 - box[1] * wRatio / 2)
            y2 = int(y2 / 2 + box[1] * wRatio / 2)
        else:
            x1 = int(x2 / 2 - box[0] * hRatio / 2)
            x2 = int(x2 / 2 + box[0] * hRatio / 2)
        img = img.crop((x1, y1, x2, y2))

    # Resize the image with best quality algorithm ANTI-ALIAS
    img.thumbnail(box, Image.ANTIALIAS)

    # save it into a file-like object
    img.save(out, "JPEG", quality=quality)

class StoreError (StandardError):
    def __init__(self, msg):
        super(msg)

class NotFoundError (StoreError):
    pass

class Store:
    """ return some key name """
    def save(self, fp, mimetype, filename):
        raise NotImplementedError

    def get(self, dest_fp):
        raise NotImplementedError

    def deliver_image(self, key, size):
        raise NotImplementedError

    def delete(self, key):
        raise NotImplementedError

class LocalStore:
    def __init__(self, root):
        self.root = root

    def save(self, fp, mimetype='application/octet-stream'):
        key = unique_id()
        filename = self.root + '/' + key
        with open(filename, 'w') as dest:
            dest.write(fp.read())
        return key

    def thumbnail_path(self, key, size):
        check_store_key(key)
        return self.root + '/' + key + ('_%sx%s' % (size))

    def path(self, key):
        check_store_key(key)
        return self.root + '/' + key

    def create_thumbnail(self, key, size):
        check_store_key(key)
        image = Image.open(self.path(key))
        with open(self.thumbnail_path(key, size), 'w') as out:
            resize(image, size, False, out)

    def deliver_image(self, key, size=None):
        check_store_key(key)
        if size != None:
            path = self.thumbnail_path(key, size)
            try:
                os.stat(path)
            except OSError:
                self.create_thumbnail(key, size)
            return self.deliver_file(self.thumbnail_path(key, size))
        else:
            return self.deliver_file(self.path(key))

    def deliver_file(self, path):
        return send_file(path, magic.from_file(path))

    def delete(self, key):
        check_store_key(key)
        os.remove(self.path(key))

def create_upload_group():
    return time.strftime('%Y%m%d_') + unique_id()

class S3Store (Store):
    def __init__(self, credentials, bucket, prefix=''):
        self.s3 = boto.connect_s3(**credentials).get_bucket(bucket)
        self.prefix = prefix

    def thumbnail_key(self, key, size):
        return key + ('_%sx%s' % (size))

    # this is rather inefficient but it's impossible to create a PIL Image directly from an S3
    # key as it doesn't support seeking. Therefore, the file is saved to a local temp file which
    # is then scaled and saved to a local temp file again because boto s3 keys do not support writing. 
    def create_thumbnail(self, key, size):
        s3_key = self.s3.get_key(self.prefix + key)
        thumb_s3_key = self.s3.new_key(self.prefix + self.thumbnail_key(key, size))

        in_tmp = tempfile.TemporaryFile()
        in_tmp.write(s3_key.read())
        in_tmp.seek(0)
        try:
            img = Image.open(in_tmp)
            out_tmp = tempfile.TemporaryFile()
            try:
                resize(img, size, False, out_tmp)
                out_tmp.seek(0)
                thumb_s3_key.set_contents_from_file(out_tmp)
            finally:
                out_tmp.close()
        finally:
            in_tmp.close()

    def deliver_image(self, key, size=None):
        if size:
            thumb_key = self.thumbnail_key(key, size)
            if self.s3.get_key(self.prefix + thumb_key) == None:
                self.create_thumbnail(key, size)
            return self.deliver_file(self.prefix + thumb_key)
        else:
            return self.deliver_file(self.prefix + key)

    def deliver_file(self, key):
        if key:
            url = self.s3.get_key(key).generate_url(3600)
            return redirect(url, 307)
        else:
            abort(404)

    def save(self, fp, mimetype='application/octet-stream'):
        key_name = unique_id()
        key = self.s3.new_key(self.prefix + key_name)
        key.set_contents_from_file(fp)
        return key_name

    def delete(self, key):
        self.s3.get_key(self.prefix + key).delete()

from simples3 import S3Bucket

class SimpleS3Store(Store):
    def __init__(self, credentials, bucket, baseurl, prefix=''):
        self.credentials = credentials
        self.bucket_name = bucket
        self.prefix = prefix
        self.baseurl = baseurl

    # TODO is simples3.S3Bucket safe to re-use?
    def bucket(self):
        return S3Bucket(str(self.bucket_name),
                        str(self.credentials['aws_access_key_id']),
                        str(self.credentials['aws_secret_access_key']),
                        str(self.baseurl)) 
                                      
    def thumbnail_key(self, key, size):
        return key + ('_%sx%s' % (size))

    # this is rather inefficient but it's impossible to create a PIL Image directly from an S3
    # key as it doesn't support seeking. Therefore, the file is saved to a local temp file which
    # is then scaled and saved to a local temp file again because boto s3 keys do not support writing. 
    # TODO still valid with simples3?
    def create_thumbnail(self, key, size):
        b = self.bucket()
        s3_key = self.prefix + key
        thumb_s3_key = self.prefix + self.thumbnail_key(key, size)

        in_tmp = tempfile.TemporaryFile()
        in_tmp.write(b.get(s3_key).read())
        in_tmp.seek(0)
        try:
            img = Image.open(in_tmp)
            out_tmp = tempfile.TemporaryFile()
            try:
                resize(img, size, False, out_tmp)
                out_tmp.seek(0)
                b.put(thumb_s3_key, out_tmp.read(), mimetype='image/jpeg')
            finally:
                out_tmp.close()
        finally:
            in_tmp.close()

    def deliver_image(self, key, size=None):
        check_store_key(key)
        if size:
            b = self.bucket()
            try:
                thumb_s3_key = self.prefix + self.thumbnail_key(key, size) 
                b.info(thumb_s3_key)
            except KeyError:
                self.create_thumbnail(key, size)
            return self.deliver_file(thumb_s3_key)
        else:
            return self.deliver_file(self.prefix + key)

    def deliver_file(self, s3_key):
        url = self.bucket().make_url_authed(s3_key, 3600)
        return redirect(url, 307)

    def save(self, fp, mimetype='application/octet-stream'):
        key_name = unique_id()
        b = self.bucket()
        s3_key = self.prefix + key_name
        b.put(s3_key, fp.read(), mimetype=mimetype)
        return key_name

    def delete(self, key):
        check_store_key(key)
        self.bucket().delete(self.prefix + key)
