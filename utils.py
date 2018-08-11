import os
import chardet
from binascii import b2a_hex
from pdfxplr import printout

ENCODINGS = ['utf-8','utf-16','ascii','mac-roman']
# http://www.exiv2.org/tags.html
IMAGE_METADATA = [

    'ProcessingSoftware',
    'BodySerialNumber',
    'LensSerialNumber',
    'GPSInfo',
    'LocalizedCameraModel',
    'OriginalRawFileName',
    'ProfileName',
    'PreviewDateTime',
    'CameraOwnerName',
    'CameraSerialNumber',
    'ImageDescription',
    'DocumentName',
    'Artist',
    'HostComputer',
    'Copyright',
    'ImageResources',
    'GPSTag',
    'ImageNumber',
    'ImageHistory',
    'XPAuthor',
    'XPKeywords',
    'XPComment',
    'XPTitle',
    'XPSubject',
    'UniqueCameraModel',
    'Make',
    'Model',
    'Software',
    'DateTime',
    'DateTimeOriginal',
    'DateTimeDigitized',
    'UserComment',
]

def try_parse_string(v,encoding=None):

    global ENCODINGS

    # If encoding was passed as an argument
    if encoding:
        try:
            v = v.decode(encoding)
            return v
        except:
            printout('[!] Error. Unable to decode string using provided encoding %s' % encoding, always=False)
            pass

    try:
        encoding = chardet.detect(v)
        printout('[*] Detected encoding %s'% encoding['encoding'], always=False)
        v = v.decode(encoding['encoding'])
        return v
    except Exception as ex:
        try:
            v = str(v)
        except Exception as exx:
            printout('[!] Error while decoding string')
            printout(ex,False)
            printout(exx,False)

    # we can try to detect encoding from the xml 

    # finally we try all possible encodings
    for e in ENCODINGS:
        try:
            v = v.decode(e)
            return v
        except:
            printout('[!] Error. Unable to decode string using encoding %s'% e, always=False)

    return v


def write_file (folder, filename, filedata, flags='w'):
    """Write the file data to the folder and filename combination
    (flags: 'w' for write text, 'wb' for write binary, use 'a' instead of 'w' for append)"""
    result = False
    if os.path.isdir(folder):
        try:
            file_obj = open(os.path.join(folder, filename), flags)
            file_obj.write(filedata)
            file_obj.close()
            result = True
        except IOError:
            pass
    return result


def determine_image_type (stream_first_4_bytes):
    """Find out the image file type based on the magic number comparison of the first 4 (or 2) bytes"""
    file_type = None
    bytes_as_hex = b2a_hex(stream_first_4_bytes)
    if bytes_as_hex.startswith(b'ffd8'):
        file_type = '.jpeg'
    elif bytes_as_hex == '89504e47':
        file_type = '.png'
    elif bytes_as_hex == '47494638':
        file_type = '.gif'
    elif bytes_as_hex.startswith(b'424d'):
        file_type = '.bmp'
    return file_type


def convert_to_degress(value):
    # taken from https://gist.github.com/erans/983821/e30bd051e1b1ae3cb07650f24184aa15c0037ce8
    d0 = value[0][0]
    d1 = value[0][1]
    d = float(d0) / float(d1)

    m0 = value[1][0]
    m1 = value[1][1]
    m = float(m0) / float(m1)

    s0 = value[2][0]
    s1 = value[2][1]
    s = float(s0) / float(s1)


    return d + (m / 60.0) + (s / 3600.0)

def human_gps_info(gpsinfo):

    # if there is all necessary information to compute a gps location, let's do it
    if set(['GPSLongitude', 'GPSLongitudeRef', 'GPSLatitude', 'GPSLatitudeRef']) > set(gpsinfo.keys()):
        return None

    lat = convert_to_degress(gpsinfo['GPSLongitude'])
    if gpsinfo['GPSLongitudeRef'] != "N":
        lat = 0 - lat
    lon = convert_to_degress(gpsinfo['GPSLatitude'])
    if gpsinfo['GPSLatitudeRef'] != "E":
        lon = 0 - lon

    return '%s,%s' % (lat,lon)