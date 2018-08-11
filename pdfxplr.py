import re
import os
import io
import sys
import rex
import html
import time
import argparse
import dumppdf
import xmpparser
from utils import *
from PIL import Image
from PIL.ExifTags import TAGS, GPSTAGS
from io import StringIO
from dateutil import parser as dateparser
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfinterp import PDFResourceManager, PDFPageInterpreter
from pdfminer.converter import PDFPageAggregator
from pdfminer.layout import LAParams, LTTextBox, LTTextLine, LTFigure, LTImage, LTChar
from pdfminer.pdftypes  import PDFObjRef, resolve1

LOCATIONS = [] # TODO: dont use a global variable
VERBOSE = False
OUTFILE = None
ENCODING = None


# TODO
# - fix pdfminer issue with some documents' metadata (mayb mac?)
# - fix encoding errors

def extract_images(doc, store_path, filename):

    rsrcmgr = PDFResourceManager()
    laparams = LAParams()
    device = PDFPageAggregator(rsrcmgr, laparams=laparams)
    interpreter = PDFPageInterpreter(rsrcmgr, device)
    p = 0
    res = []

    for page in PDFPage.create_pages(doc):
        p += 1
        try:
            interpreter.process_page(page)
            pdf_item = device.get_result()

            for thing in pdf_item:
                if isinstance(thing, LTImage):
                    res.append(extract_image_metadata(t,store_path,page_number=p,filename=filename))
                if isinstance(thing, LTFigure):
                    for t in thing:
                        if isinstance(t, LTImage):
                            res.append(extract_image_metadata(t,store_path,page_number=p,filename=filename))

        except Exception as ex:
            printout('[!] Impossible to process page %d' % p, False)
            printout(ex)

    return res


def extract_image_metadata(lt_image, store_path, page_number, filename):

    metadata = {}
    image_name = ''.join([filename, '_', str(page_number), '_', lt_image.name])
    metadata['local_file'] = image_name

    if lt_image.stream:
        try:

            file_stream = lt_image.stream.get_rawdata()
            image = io.BytesIO(file_stream)
            img = Image.open(image)        
            for (tag,value) in img._getexif().items():

                tag_name = TAGS.get(tag)

                if tag_name == 'GPSInfo':
                    gps_info = {}
                    for g in value:
                        gps_tag_name = GPSTAGS.get(g, g)
                        gps_info[gps_tag_name] = value[g]
                    metadata = dict(metadata, **gps_info)
                    # if we can compute a location
                    location = human_gps_info(gps_info)                    
                    metadata['_Location'] = location

                elif tag_name in IMAGE_METADATA:
                    printout('Found tag %s' % tag_name,False)
                    metadata[tag_name] = try_parse_string(value, ENCODING)

        except Exception as ex:
            printout(ex,False)

        # if we need to store the image
        if file_stream and store_path:

            file_ext = determine_image_type(file_stream[0:4])
            file_name = '%s%s' % (image_name,file_ext)
            if file_ext: write_file(store_path, file_name, file_stream, flags='wb')

    return metadata


def get_metadata(doc):

    metadata = {}

    try:

        # get language info from "catalog" dictionary
        if 'Lang' in doc.catalog.keys(): 
            metadata['Lang'] = doc.catalog['Lang'].decode('utf-8')
        # if metadata is in the catalog 
        if 'Metadata' in doc.catalog:
            old_meta = resolve1(doc.catalog['Metadata']).get_data()
            #print(metadata)  # The raw XMP metadata
            old_dict = (xmpparser.xmp_to_dict(old_meta))
            try:
                metadata['catalog:Producer'] = old_dict['pdf']['Producer']
                metadata['catalog:creator'] = old_dict['dc']['creator']
                metadata['catalog:CreatorTool'] = old_dict['xap']['CreatorTool']
                metadata['catalog:CreateDate'] = old_dict['xap']['CreateDate']
                metadata['catalog:ModifyDate'] = old_dict['xap']['ModifyDate']
            except Exception as ex:
                printout('[!] Error while parsing old metadata format')
                printout(ex)
        # get metadata from "info" list of dicts
        for i in doc.info:
            for k,v in i.items():

                # let's get rid of strange encodings 
                v = try_parse_string(v,ENCODING)

                # let's get the dates
                if k in ['ModDate','CreationDate']:
                    # compute date (http://www.verypdf.com/pdfinfoeditor/pdf-date-format.htm)  
                    try:
                        v = time.strptime(v[2:].replace('\'',''),"%Y%m%d%H%M%S%z")
                    except Exception as ex:
                        try:
                            v = dateparser.parse(v)
                        except Exception as exx:
                            printout('[!] Error while parsing date')
                            printout(ex)
                            printout(exx)
                            v = '%s [RAW]' % v
                # let's consider cases in which there is more than one "info" block
                c = 0
                while k in metadata.keys():
                    c = c + 1
                    k = '%s-%d' % (k,c)
                metadata[k] = v
    except Exception as ex:
        printout('[!] Error while retrieving metadata')
        printout(ex)

    return metadata


def get_xml(file):

    io = StringIO()
    dumppdf.dumppdf(io, file, [], set(), '', dumpall=True, codec=None, extractdir=None)
    return io.getvalue()


def retrieve_all(xml, regex):

    return re.findall(regex, xml)


def paths_in_tooltips(xml):

    regex = re.compile(r'<value><string size="[0-9]+">(.*?[\\|/|.].*?)</string></value>')
    paths = []
    alt_flag = False
    inside_flag = False

    for line in xml:

        if alt_flag:
            nupaths = re.findall(regex, line)
            for p in nupaths:
                paths.append(try_parse_string(p,ENCODING))
            inside_flag = False
            alt_flag = False
            continue

        if '<value><literal>' in line:
            inside_flag = True
            continue

        if inside_flag and '<key>Alt</key>' in line:
            alt_flag = True
            continue

    return paths


def printout(message='', always=True):
    
    if VERBOSE or always:
        if OUTFILE:
            with io.open(OUTFILE, 'a',encoding='utf-16') as f:
                print(message,file=f)
        if not OUTFILE or VERBOSE:
            print(message)


def print_metadata(filename,metadata):

    printout('%s: %s' % ('File'.ljust(20),filename),True)
    for k,v in metadata.items():
        if isinstance(v, time.struct_time):
            v = time.strftime("%a, %d %b %Y %H:%M:%S +0000", v)
        printout('%s: %s' % (k.ljust(20),v),True)
    printout('',True)


def print_image_metadata(meta):

    for i in meta:
        for m in i:
            if len(m) > 1:

                printout('[Metadata for image %s]' % m['local_file'])
                for k in m.keys():
                    if k != 'local_file': printout('\t%s: %s' % (k.ljust(20), m[k]))
                printout('')


def get_users_sw_from_img_meta(metadata):

    users = []
    sw = []
    serials = []
    locations = []

    for m in metadata:
        if 'ProcessingSoftware' in m.keys():
            sw.append(m['ProcessingSoftware'])
        if 'Software' in m.keys():
            sw.append(m['Software'])
        if 'CameraOwnerName' in m.keys():
            users.append(m['CameraOwnerName'])
        if 'Artist' in m.keys():
            users.append(m['Artist'])
        if 'HostComputer' in m.keys():
            users.append(m['HostComputer'])
        if 'Copyright' in m.keys():
            users.append(m['Copyright'])
        if 'XPAuthor' in m.keys():
            users.append(m['XPAuthor'])
        if 'BodySerialNumber' in m.keys():
            serials.append(m['BodySerialNumber'])
        if 'LensSerialNumber' in m.keys():
            serials.append(m['LensSerialNumber'])
        if 'CameraSerialNumber' in m.keys():
            serials.append(m['CameraSerialNumber'])
        if '_Location' in m.keys():
            locations.append(m['_Location'])


    return [users,sw,serials,locations]    


def get_users_sw_from_meta(metadata):

    users = []
    sw = []

    for k,v in metadata.items():
        if 'author' in k.lower():
            users.append(v)
        if 'catalog:creator' == k.lower():
            users.append(''.join(v))
        elif 'creator' in k.lower():
            sw.append(v)
        elif 'producer' in k.lower():
            sw.append(v)

    return [users,sw]


def get_info_from_paths(paths):

    u_linux = []
    u_mac = []
    u_windows = []

    for p in paths:
        u_windows += re.findall(rex.RE_USERNAME_WINDOWS, p)
        u_mac += re.findall(rex.RE_USERNAME_MAC, p)
        u_linux += re.findall(rex.RE_USERNAME_LINUX, p)

    return [u_linux,u_mac,u_windows]


def main():

    global OUTFILE, VERBOSE, ENCODING

    parser = argparse.ArgumentParser(description='extract interesting data from pdf files.')
    parser.add_argument('path', metavar='PATH', type=str, help='path to a file or folder')
    parser.add_argument('-c', '--encoding', metavar='encoding', type=str, help='encoding used by the document')
    parser.add_argument('-m', '--metadata', action='store_true', help='print metadata - turned off by default')
    parser.add_argument('-e', '--email', action='store_true', help='extract all email addresses')
    parser.add_argument('-l', '--links', action='store_true', help='extract all URLs')
    parser.add_argument('-i', '--ips', action='store_true', help='extract all IP addresses')
    parser.add_argument('-p', '--paths', action='store_true', help='extract paths and filenames from image alternative text field')
    parser.add_argument('-u', '--usernames', action='store_true', help='show all usernames identified')
    parser.add_argument('-s', '--software', action='store_true', help='show all software components identified')
    parser.add_argument('-x', '--images', action='store_true', help='extract information from embedded - use with -m to list image metadata')
    parser.add_argument('-a', '--all', action='store_true', help='extract all - does not print metadata without -m switch')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    parser.add_argument('-o', '--outfile', nargs='?', const='list', default=None, help='output file path')
    parser.add_argument('--store-images', nargs='?', const='list', default=None, help='path where to store extracted images')

    args = parser.parse_args(args=None if len(sys.argv) > 1 else ['--help'])

    if args.store_images and not (args.images or args.all):
        printout('[!] Error. Switch --images is necessary for --store-images')
        sys.exit(0)

    if args.encoding:
        ENCODING = args.encoding

    if args.all:
        args.email = args.links = args.ips = args.paths = args.usernames = args.software = args.images = True

    if args.outfile:
        OUTFILE = args.outfile

    VERBOSE = args.verbose

    extract_paths = args.paths

    # some options depend on other information being extracted
    if args.usernames:
        extract_paths = True

    links = set()
    emails = set()
    usernames = set()
    ips = set()
    paths = set()
    softwares = set()
    locations = set()
    img_users = set()
    img_software = set()
    img_locations = set()
    img_serials = set()
    pdf_metadata = []
    img_metadata = []


    # get all input files
    if os.path.isfile(args.path):
        files = [args.path]
    elif os.path.isdir(args.path):
        files = [os.path.join(args.path,f) for f in os.listdir(args.path) if os.path.isfile(os.path.join(args.path,f)) and f.endswith('.pdf')]
        printout('Files to be processed:')
        for h in files:
            printout(' %s' % os.path.join(args.path,h))
    else:
        printout('[!] Error: provided path %s is not a valid file or folder' % args.path)
        sys.exit(-1)

    for f in files:
        with open(f, 'rb') as fp:

            try:

                printout('[*] Processing file %s...' % f, True)
                printout('',True)
                parser = PDFParser(fp)
                doc = PDFDocument(parser)
                metadata = get_metadata(doc)
                if args.metadata:
                    print_metadata(f,metadata)
                if args.email or args.links or args.ips or args.paths or args.usernames or args.software:
                    xml = get_xml(f)
                    decoded = html.unescape(xml)
                if args.email:
                    emails |= set(retrieve_all(decoded,rex.RE_EMAIL))
                if args.links:
                    links |= set(retrieve_all(decoded,rex.RE_WWW))
                if args.ips:
                    ips |= set(retrieve_all(decoded,rex.RE_IP))
                if extract_paths:
                    paths |= set(paths_in_tooltips(decoded.splitlines()))
                if args.usernames or args.software:
                    [u,s] = get_users_sw_from_meta(metadata)
                    usernames |= set(u)
                    softwares |= set(s)
                if args.images:
                    image_meta = extract_images(doc, store_path=args.store_images,filename=f)
                    img_metadata.append(image_meta)
                    [img_u,img_sw,img_ser,img_loc] = get_users_sw_from_img_meta(image_meta)    
                    img_users |= set(img_u) 
                    img_software |= set(img_sw)
                    img_locations |= set(img_loc)
                    img_serials |= set(img_ser)
            except Exception as ex: 
                printout('[!] Error while processing file %s' % f)
                printout()
                printout(ex,False)


    # now we also retrieve info from the paths structure found
    [u_linux,u_mac,u_windows]  = get_info_from_paths(paths)
    usernames |= set(u_linux)
    usernames |= set(u_mac)
    usernames |= set(u_windows)

    if args.images and args.metadata:
        printout('[*] IMAGE METADATA')
        printout()
        print_image_metadata(img_metadata)

    if args.usernames:
        printout('[*] USERNAMES FOUND: %d' % len(usernames))
        for e in usernames:
            printout('\t%s' % e)
        printout()
    if args.paths:
        printout('[*] PATHS FOUND: %d' % len(paths))
        for e in paths:
            printout('\t%s' % e)
        printout()
    if args.ips:
        printout('[*] IPS FOUND: %d' % len(ips))
        for e in ips:
            printout('\t%s' % e)
        printout()
    if args.email:
        printout('[*] EMAILS FOUND: %d' % len(emails))
        for e in emails:
            printout('\t%s' % e)
        printout()
    if args.links:
        printout('[*] LINKS FOUND: %d' % len(links))
        for e in links:
            printout('\t%s' % e)
        printout()
    if args.software:
        printout('[*] SOFTWARE FOUND: %d' % len(softwares))
        for e in softwares:
            printout('\t%s' % e)
        printout()
    if args.images:
        if img_users and args.usernames:
            printout('[*] USERS FOUND IN IMAGES: %s' % len(img_users))
            for e in img_users:
                printout('\t%s' % e)
            printout()
        if img_software and args.software:
            printout('[*] SOFTWARE FOUND IN IMAGES: %s' % len(img_software))
            for e in img_software:
                printout('\t%s' % e)
            printout()
        if img_locations:
            printout('[*] LOCATIONS FOUND IN IMAGES: %s' % len(img_locations))
            for e in img_locations:
                printout('\t%s' % e)
            printout()
        if img_serials:
            printout('[*] SERIALS FOUND IN IMAGES: %s' % len(img_serials))
            for e in img_serials:
                printout('\t%s' % e)
            printout()


if __name__ == '__main__':
    main()