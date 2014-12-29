# encoding: utf-8
import random, os, magic, Image, base64, struct, time, mimetypes
from flask import redirect
from flask.helpers import send_file
from util import check_store_key
from simples3 import S3Bucket

def unique_id():
    return base64.urlsafe_b64encode(struct.pack('fHH', time.time(), os.getpid() % 65536, random.randint(0, 65535))).replace('=', '')

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

class FileCache:
    def __init__(self, cache_dir='/tmp/tamaraw/image_cache'):
        self.cache_dir = cache_dir

    def path(self, key):
        return self.cache_dir + '/' + key
    
    def __contains__(self, key):
        try:
            os.stat(self.path(key))
            return True
        except OSError:
            return False
    
    def open(self, key, mode='r'):
        return open(self.path(key), mode)
        
    # the idea is to call this from a cron job
    # this function should analyze an nginx log file and determine which
    # images should be cached, possibly evicting seldomly requested ones
    # and downloading additional ones which have dropped out of the cache.
    # this is necessary because the s3 store class only fills the cache
    # when convenient
    def manage(self, log_file, max_size):
        raise NotImplementedError

class SimpleS3Store(Store):
    def __init__(self, credentials, bucket, baseurl, logger, prefix, cache=FileCache()):
        self.credentials = credentials
        self.bucket_name = bucket
        self.prefix = prefix
        self.logger = logger
        self.baseurl = baseurl
        self.cache = cache

    # TODO is simples3.S3Bucket safe to re-use?
    def bucket(self):
        return S3Bucket(str(self.bucket_name),
                        str(self.credentials['aws_access_key_id']),
                        str(self.credentials['aws_secret_access_key']),
                        str(self.baseurl)) 
                                      
    def thumbnail_key(self, key, size):
        return key + ('_%sx%s' % (size))
    
    def default_headers(self, filename):
        return {'Content-Disposition': 'inline; filename=%s' % (filename,),
                'Cache-Control': 'public max-age=86400'}

    def create_thumbnail(self, key, size):
        b = self.bucket()
        s3_key = self.prefix + key
        thumb_key = self.thumbnail_key(key, size)

        if key in self.cache:
            in_tmp = self.cache.open(key + '.jpg')
        else:
            # todo guess correct extension
            in_tmp = self.cache.open(key + '.jpg', 'w+b')
            in_tmp.write(b.get(s3_key).read())
            in_tmp.seek(0)
        try:
            img = Image.open(in_tmp)
            out_tmp = self.cache.open(thumb_key + '.jpg', 'w+b')
            try:
                resize(img, size, False, out_tmp)
                out_tmp.seek(0)
                thumb_s3_key = self.prefix + thumb_key
                b.put(thumb_s3_key, out_tmp.read(), mimetype='image/jpeg',
                      headers=self.default_headers(thumb_s3_key))
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
        # check again if it's in the cache. if a thumbnail was newly
        # created, it is now locally available. TODO guess extension?
        key_no_prefix = s3_key.replace(self.prefix, '')
        exts = ('.jpg', '.png')
        for ext in exts:
            cache_key = key_no_prefix + ext
            if cache_key in self.cache:
                mimetype, _ = mimetypes.guess_type(cache_key)
                return send_file(self.cache.path(cache_key), mimetype) 
        url = self.bucket().make_url_authed(s3_key, 3600)
        return redirect(url, 307)

    def save(self, fp, mimetype='application/octet-stream'):
        key_name = unique_id()
        s3_key = self.prefix + key_name
        # ".jpe" would have been my first choice for naming jpegs.. not
        ext = mimetypes.guess_extension(mimetype).replace('jpe', 'jpg')
        content = fp.read()
        with self.cache.open(key_name + ext, 'w') as cache_file:
            cache_file.write(content)
        self.bucket().put(s3_key, content, mimetype=mimetype,
                          headers=self.default_headers(s3_key + ext))
        return key_name

    def delete(self, key):
        check_store_key(key)
        b = self.bucket()
        for s3_key, _, _, _ in b.listdir(self.prefix + key):
            self.logger.info('deleting s3 key %s', s3_key)
            b.delete(s3_key)
