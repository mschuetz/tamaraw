import random, os, magic, Image, re, base64, struct, boto, time
from flask import abort, redirect
from flask.helpers import send_file
import tempfile

def unique_id():
    return base64.urlsafe_b64encode(struct.pack('fHH', time.time(), os.getpid(), random.randint(0, 65536))).replace('=', '_')

# http://united-coders.com/christian-harms/image-resizing-tips-every-coder-should-know/
def resize(img, box, fit, out, quality=90):
    '''Downsample the image.
    @param img: Image -  an Image-object
    @param box: tuple(x, y) - the bounding box of the result image
    @param fix: boolean - crop the image to fill the box
    @param out: file-like-object - save the image into the output stream
    '''
    #preresize image with factor 2, 4, 8 and fast algorithm
    factor = 1
    while img.size[0]/factor > 2*box[0] and img.size[1]*2/factor > 2*box[1]:
        factor *=2
    if factor > 1:
        img.thumbnail((img.size[0]/factor, img.size[1]/factor), Image.NEAREST)

    #calculate the cropping box and get the cropped part
    if fit:
        x1 = y1 = 0
        x2, y2 = img.size
        wRatio = 1.0 * x2/box[0]
        hRatio = 1.0 * y2/box[1]
        if hRatio > wRatio:
            y1 = int(y2/2-box[1]*wRatio/2)
            y2 = int(y2/2+box[1]*wRatio/2)
        else:
            x1 = int(x2/2-box[0]*hRatio/2)
            x2 = int(x2/2+box[0]*hRatio/2)
        img = img.crop((x1,y1,x2,y2))

    #Resize the image with best quality algorithm ANTI-ALIAS
    img.thumbnail(box, Image.ANTIALIAS)

    #save it into a file-like object
    img.save(out, "JPEG", quality=quality)

class StoreError (StandardError):
    def __init__(self, msg):
        super(msg)
        
class NotFoundError (StoreError):
    pass

class Store:
    """ return some key name """
    def save(self, fp):
        raise NotImplementedError

    def get(self, dest_fp):
        raise NotImplementedError

    def deliver_image(self, key, size):
        raise NotImplementedError

class LocalStore:
    def __init__(self, root):
        self.root = root
    
    def save(self, fp):
        key = unique_id()
        filename = self.root + '/' + key
        with open(filename, 'w') as dest:
            dest.write(fp.read())
        return key

    def thumbnail_path(self, key, size):
        return self.root + '/' + key + ('_%sx%s' % (size))

    def path(self, key):
        return self.root + '/' + key

    def create_thumbnail(self, key, size):
        image = Image.open(self.path(key))
        with open(self.thumbnail_path(key, size), 'w') as out:
            resize(image, size, False, out)

    def deliver_image(self, key, size=None):
        if not re.match('^[_0-9a-zA-Z]+$', key):
            abort(404)
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

def create_upload_group():
    return time.strftime('%Y%m%d_') + unique_id()

class S3Store (Store):
    def __init__(self, credentials, bucket, prefix=''):
        self.s3 = boto.connect_s3(**credentials).get_bucket(bucket)
        self.prefix = prefix

    def thumbnail_key(self, key, size):
        return key + ('_%sx%s' % (size))

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
            
    def save(self, fp):
        key_name = unique_id()
        key = self.s3.new_key(self.prefix + key_name)
        key.set_contents_from_file(fp)
        return key_name
