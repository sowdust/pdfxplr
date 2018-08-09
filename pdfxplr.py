import re
import os
import io
import sys
import rex
import html
import time
import dumppdf
import argparse
import chardet

from io import StringIO
from dateutil import parser as dateparser
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument

VERBOSE = False
OUTFILE = None


def printout(message='', always=True):
    if VERBOSE or always:
        if OUTFILE:
            with io.open(OUTFILE, 'a',encoding='utf-16') as f:
                print(message,file=f)
        if not OUTFILE or VERBOSE:
            print(message)


def get_metadata(file):
    metadata = {}
    with open(file, 'rb') as fp:
        parser = PDFParser(fp)
        doc = PDFDocument(parser)
        # get language info from "catalog" dictionary
        if 'Lang' in doc.catalog.keys(): 
            metadata['Lang'] = doc.catalog['Lang'].decode('utf-8')

        # get metadata from "info" list of dicts
        for i in doc.info:
            for k,v in i.items():

                # let's get rid of strange encodings 
                try:
                	encoding = chardet.detect(v)
                	v = v.decode(encoding['encoding'])
                except Exception as ex:
                	try:
                		v = str(v)
                	except Exception as exx:
	                    printout('[!] Error while decoding string')
	                    printout(ex)
	                    printout(exx)

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
                            printout.error(exx)
                            v = '%s [RAW]' % v
                # let's consider cases in which there is more than one "info" block
                c = 0
                while k in metadata.keys():
                    c = c + 1
                    k = '%s-%d' % (k,c)
                metadata[k] = v

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
            paths += re.findall(regex, line)
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

def print_metadata(filename,metadata):
    printout('%s%s' % ('File'.ljust(15),filename),True)
    for k,v in metadata.items():
        if isinstance(v, time.struct_time):
            v = time.strftime("%a, %d %b %Y %H:%M:%S +0000", v)
        printout('%s%s' % (k.ljust(15),v),True)
    printout('',True)


def get_users_sw_from_meta(metadata):
    users = []
    sw = []

    for k,v in metadata.items():
        if 'author' in k.lower():
            users.append(v)
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

    global OUTFILE, VERBOSE

    parser = argparse.ArgumentParser(description='Extract interesting data from pdf files.')
    parser.add_argument('path', metavar='PATH', type=str, help='Path to a file or folder')
    parser.add_argument('-m', '--metadata', action='store_true', help='Print metadata')
    parser.add_argument('-e', '--email', action='store_true', help='Extract all email addresses')
    parser.add_argument('-l', '--links', action='store_true', help='Extract all URLs')
    parser.add_argument('-i', '--ips', action='store_true', help='Extract all IP addresses')
    parser.add_argument('-p', '--paths', action='store_true', help='Extract paths and filenames from image alternative text field')
    parser.add_argument('-u', '--usernames', action='store_true', help='')
    parser.add_argument('-s', '--software', action='store_true', help='')
    parser.add_argument('-a', '--all', action='store_true', help='Extract all - does not print metadata unless explicitly asked')
    parser.add_argument('-v', '--verbose', action='store_true', help='Verbose mode')
    parser.add_argument('-o', '--outfile', nargs='?', const='list', default=None, help='Output file path. Files will be overwritten.')

    args = parser.parse_args(args=None if len(sys.argv) > 1 else ['--help'])

    if args.all:
        args.email = args.links = args.ips = args.paths = args.usernames = args.software = True

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

    # get all input files
    if os.path.isfile(args.path):
        files = [args.path]
    elif os.path.isdir(args.path):
        files = [f for f in os.listdir(args.path) if os.path.isfile(f) and f.endswith('.pdf')]
    else:
        printout('[!] Error: provided path %s is not a valid file or folder' % args.path)
        sys.exit(-1)

    for f in files:
        metadata = get_metadata(f)
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
        del(xml)
        del(decoded)

    # now we also retrieve info from the paths structure found
    [u_linux,u_mac,u_windows]  = get_info_from_paths(paths)
    usernames |= set(u_linux)
    usernames |= set(u_mac)
    usernames |= set(u_windows)

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
        printout('[*] SOFTWARE FOUND: %d' % len(links))
        for e in softwares:
            printout('\t%s' % e)
        printout()


if __name__ == '__main__':
    main()