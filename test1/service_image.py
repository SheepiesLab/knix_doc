from PIL import Image
import glob
import os

size = 32, 32

def service(req):
    infile = 'dog.jpg'
    file, ext = os.path.splitext(infile)
    im = Image.open(infile)
    im.thumbnail(size)
    im.save(file + ".thumbnail", "JPEG")
    return {'message': 'OK', 'content': req}, 200
