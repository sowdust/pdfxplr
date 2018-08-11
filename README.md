# pdfxplr

Extract hidden data from pdf files.

### Summary

This script attempts to extract potentially interesting data from pdf files, that might be useful in penetration tests, forensics analysis or OSINT investigations.
Besides classic metadata, it searches for elements usually overlooked, including metadata inside embedded images.

### Prerequisites

You will need Python 3 with the following libraries:
* chardet
* pdfminer.six
* python-dateutil
* Pillow

```
pip install -r requirements.txt
```

### Configuration

The list of exif metadata that will be extracted is set in utils.py, as well as the list of character encodings that will be tried when all else fails.

### Usage

```
usage: pdfxplr.py [-h] [-c encoding] [-m] [-e] [-l] [-i] [-p] [-u] [-s] [-x]
                  [-a] [-v] [-o [OUTFILE]] [--store-images [STORE_IMAGES]]
                  PATH

extract interesting data from pdf files.

positional arguments:
  PATH                  path to a file or folder

optional arguments:
  -h, --help            show this help message and exit
  -c encoding, --encoding encoding
                        encoding used by the document
  -m, --metadata        print metadata - turned off by default
  -e, --email           extract all email addresses
  -l, --links           extract all URLs
  -i, --ips             extract all IP addresses
  -p, --paths           extract paths and filenames from image alternative
                        text field
  -u, --usernames       show all usernames identified
  -s, --software        show all software components identified
  -x, --images          extract information from embedded - use with -m to
                        list image metadata
  -a, --all             extract all - does not print metadata without -m
                        switch
  -v, --verbose         verbose mode
  -o [OUTFILE], --outfile [OUTFILE]
                        output file path
  --store-images [STORE_IMAGES]
                        path where to store extracted images
```

### Acknowledgments

Thanks to Gianluca Baldi for the help with the first version of this project and to Maurizio Agazzini for having suggested using the images' alt text in pdf files.

