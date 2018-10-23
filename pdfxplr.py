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


VERBOSE = False
# global vars?
OUTFILE = None 
ENCODING = None
LINEWIDTH = 78

VERSION = "0.1"
BANNER = """
pdfxplr.py v. {0} - Find hidden data in pdf
by sowdust
""".format(VERSION)

# TODO
# - add samples
# - understand why some gps are stripped and some are not (ie only gpsVersionID is there) 
# - read GPSVersionID as bytes



def get_metadata(doc):

    metadata = {}

    try:

        # get language info from "catalog" dictionary
        if 'Lang' in doc.catalog.keys(): 
            metadata['Lang'] = try_parse_string(doc.catalog['Lang'],ENCODING,VERBOSE)
        # if metadata is in the catalog 
        try:
            if 'Metadata' in doc.catalog:
                old_meta = resolve1(doc.catalog['Metadata']).get_data()
                #print(metadata)  # The raw XMP metadata
                old_dict = (xmpparser.xmp_to_dict(old_meta))

                metadata = append_catalog_metadata(metadata,old_dict)
        except Exception as ex:
            printout('[!] Error while trying to get old style metadata',False)
            printout(ex,False)



        # get metadata from "info" list of dicts
        for i in doc.info:
            for k,v in i.items():

                # resolving issue https://github.com/pdfminer/pdfminer.six/issues/172#issuecomment-419657617
                if isinstance(v, PDFObjRef):
                    v = resolve1(v)

                # let's get rid of strange encodings 
                v = try_parse_string(v,ENCODING,VERBOSE)

                # let's get the dates
                if k in ['ModDate','CreationDate']:
                    v = try_parse_date(v,ENCODING)

                # let's consider cases in which there is more than one "info" block
                c = 0
                while k in metadata.keys():
                    c = c + 1
                    k = '%s-%d' % (k,c)
                metadata[k] = v
    except Exception as ex:
        printout('[!] Error while retrieving metadata')
        printout(ex,True)

    return metadata




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
            printout(ex,False)

    return res


def extract_image_metadata(lt_image, store_path, page_number, filename):

    metadata = {}
    image_name = ''.join([filename, '_', str(page_number), '_', lt_image.name])
    metadata['_local_file'] = image_name

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
                    metadata[tag_name] = try_parse_string(value, ENCODING,VERBOSE)

        except Exception as ex:
            printout(ex,False)

        # if we need to store the image
        if file_stream and store_path:

            file_ext = determine_image_type(file_stream[0:4])
            file_name = '%s%s' % (image_name,file_ext)
            if file_ext: write_file(store_path, file_name, file_stream, flags='wb')

    return metadata



def extract_image_metadata2(lt_image, store_path, page_number, filename):

    metadata = {}
    image_name = ''.join([filename, '_', str(page_number), '_', lt_image.name])
    metadata['_local_file'] = image_name

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
                    metadata[tag_name] = try_parse_string(value, ENCODING,VERBOSE)

        except Exception as ex:
            printout(ex,False)

        # if we need to store the image
        if file_stream and store_path:

            file_ext = determine_image_type(file_stream[0:4])
            file_name = '%s%s' % (image_name,file_ext)
            if file_ext: write_file(store_path, file_name, file_stream, flags='wb')

    return metadata


def get_xml(file):
    io = StringIO()
    dumppdf.dumppdf(io, file, [], set(), '', dumpall=True, codec=None, extractdir=None)
    return io.getvalue()



def retrieve_all(xml, regex):

    return re.findall(regex, xml)


def urls_in_tags(xml):
    regex = re.compile(r'<value><string size="[0-9]+">(.*?[\\|/|.].*?)</string></value>')
    paths = []
    alt_flag = False
    inside_flag = False

    for line in xml:

        if alt_flag:
            nupaths = re.findall(regex, line)
            for p in nupaths:
                paths.append(try_parse_string(p,ENCODING,VERBOSE))
            inside_flag = False
            alt_flag = False
            continue

        if '<value><literal>' in line:
            inside_flag = True
            continue

        if inside_flag and '<key>URI</key>' in line:
            alt_flag = True
            continue

    return paths

def paths_in_tooltips(xml):

    regex = re.compile(r'<value><string size="[0-9]+">(.*?[\\|/|.].*?)</string></value>')
    paths = []
    alt_flag = False
    inside_flag = False

    for line in xml:

        if alt_flag:
            nupaths = re.findall(regex, line)
            for p in nupaths:
                paths.append(try_parse_string(p,ENCODING,VERBOSE))
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


def printout(message='', always=True):
    
    if VERBOSE or always:
        if OUTFILE:
            with io.open(OUTFILE, 'a',encoding='utf-16') as f:
                print(message,file=f)
        if not OUTFILE or VERBOSE:
            print(message)


def print_metadata(metadata):

    for f in metadata:
        if not(f): continue
        printout('%s: %s' % ('* Metadata for PDF'.ljust(20),f['_filename']))
        for k,v in f.items():
            if k != '_filename':
                if isinstance(v, time.struct_time):
                    v = time.strftime("%a, %d %b %Y %H:%M:%S +0000", v)
                printout('  %s: %s' % (k.ljust(18),v),True)
        printout('',True)    


def print_image_metadata(meta):

    for i in meta:
        for m in i:
            if len(m) > 1:
                printout('%s: %s' % ('* Metadata for img'.ljust(20),m['_local_file']))
                for k in m.keys():
                    if k != '_local_file':
                        printout('  %s: %s' % (k.ljust(18), m[k]))
                printout('')


def print_results(title,res):
    printout('%s: %s' % (title.ljust(20),len(res)))
    for r in res:
        printout('%s: %s' % (''.ljust(20), r))
    printout()


def parse_args():

    global ENCODING, OUTFILE, VERBOSE

    parser = argparse.ArgumentParser(description='extract interesting data from pdf files.')
    parser.add_argument('path', metavar='PATH', type=str, help='path to a file or folder')
    parser.add_argument('-m', '--metadata', action='store_true', help='show metadata, off by default')
    parser.add_argument('-a', '--all', action='store_true', help='show all, add -m to show also metadata')
    parser.add_argument('-e', '--email', action='store_true', help='list all email addresses')
    parser.add_argument('-l', '--links', action='store_true', help='list all URLs')
    parser.add_argument('-i', '--ips', action='store_true', help='list all IP addresses')
    parser.add_argument('-u', '--usernames', action='store_true', help='list all usernames')
    parser.add_argument('-s', '--software', action='store_true', help='list all software components identified')
    parser.add_argument('-p', '--paths', action='store_true', help='list all content found in image alt fields (ie. system paths)')
    parser.add_argument('-x', '--images', action='store_true', help='extract info from images, use -m to show metadata')
    parser.add_argument('-v', '--verbose', action='store_true', help='verbose mode')
    #parser.add_argument('-o','--outfile', metavar='outfile', type=str, help='output file path')
    parser.add_argument('--encoding', metavar='encoding', type=str, help='input document encoding')
    parser.add_argument('--store-images', metavar='path', type=str, help='path to store extracted images (optional)')

    args = parser.parse_args(args=None if len(sys.argv) > 1 else ['--help'])

    if args.store_images and not (args.images or args.all):
        printout('[!] Error. Switch --images is necessary for --store-images')
        sys.exit(0)

    if args.store_images and not os.path.isdir(args.store_images):
        printout('[!] Error. Not a valid path to store images: %s' % args.store_images)
        sys.exit(0)

    if args.encoding:
        ENCODING = args.encoding

    if args.all:
        args.email = args.links = args.ips = args.paths = args.usernames = args.software = args.images = True

    args.summary = args.email or args.links or args.ips or args.paths or args.usernames or args.software

    # if args.outfile:        OUTFILE = args.outfile

    VERBOSE = args.verbose

    args.extract_paths = args.paths

    # some options depend on other information being extracted
    if args.usernames:
        args.extract_paths = True

    return args



def main():

    global OUTFILE, VERBOSE, ENCODING

    printout(BANNER)

    args = parse_args()

    
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
        printout('Files to be processed:',False)
        for h in files:
            printout(' %s' % os.path.join(args.path,h),False)
    else:
        printout('[!] Error: provided path %s is not a valid file or folder' % args.path)
        sys.exit(-1)

    # extract data from all files
    for f in files:
        with open(f, 'rb') as fp:

            try:

                if VERBOSE:
                    printout('* Processing file %s...' % f)
                else:
                    print(' ' * 200, end='\r')
                    print('* Processing file %s...' % f, end='\r')
                
                parser = PDFParser(fp)
                doc = PDFDocument(parser)
                if not doc.is_extractable:
                    printout('[!] Document %s is set not to be extractable. Trying anyway...' % f)
                    doc.is_extractable = True
                metadata = get_metadata(doc)
                metadata['_filename'] = f
                pdf_metadata.append(metadata)
                if args.email or args.links or args.ips or args.paths or args.usernames or args.software:
                    xml = get_xml(f)
                    decoded = html.unescape(xml)
                if args.email:
                    emails |= set(retrieve_all(decoded,rex.RE_EMAIL))
                if args.links:
                    links |= set(retrieve_all(decoded,rex.RE_WWW))
                    links |= set(urls_in_tags(decoded.splitlines()))
                if args.ips:
                    ips |= set(retrieve_all(decoded,rex.RE_IP))
                if args.extract_paths:
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
                printout('[!] Error while processing file %s: %s' % (f,ex))
                printout()
                printout(ex,False)

    # now we also retrieve info from the paths structure found
    [u_linux,u_mac,u_windows]  = get_info_from_paths(paths)
    usernames |= set(u_linux)
    usernames |= set(u_mac)
    usernames |= set(u_windows)

    # if images were extracted and metadata to be shown, first show img metadata
    if args.metadata and args.images:
        printout('%s %s %s' % ('.' * 31, 'image metadata', '.' * 31))
        printout()
        print_image_metadata(img_metadata)
    # show pdf metadata
    if args.metadata:
        printout('%s %s %s' % ('.' * 32, 'PDF metadata', '.' * 32))
        printout()
        print_metadata(pdf_metadata)

    # print the summary of results
    if args.summary: printout('.' * 78 + '\n')
    if args.usernames: print_results('* Usernames found',usernames)
    if args.paths: print_results('* Paths found',paths)
    if args.ips: print_results('* IPs found',ips)
    if args.email: print_results('* Emails found',emails)
    if args.links: print_results('* Links found',links)
    if args.software: print_results('* Software found',softwares)
    if args.images:
        if img_users and args.usernames: print_results('* Users in images',img_users)
        if img_software and args.software: print_results('* Software in images',img_software)
        if img_locations: print_results('* GPS Locations', img_locations)
        if img_serials: print_results('* Serial # in images', img_serials)

if __name__ == '__main__':
    main()

