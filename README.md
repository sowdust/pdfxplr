# pdfxplr

Extract hidden data from pdf files.

### Summary

This script attempts to extract potentially interesting data from pdf files, that might be useful in penetration tests, forensics analysis or OSINT investigations.
Besides classic metadata, it searches for elements usually overlooked, such as the alternative text set for images, which by default in Microsoft Office documents is the full path of the image file.

### Prerequisites

You will need Python 3 with the following libraries:
* chardet
* pdfminer.six
* python-dateutil

```
pip install -r requirements.txt
```

### Usage

```
usage: pdfxplr.py [-h] [-m] [-e] [-l] [-i] [-p] [-u] [-s] [-a] [-v]
                  [-o [OUTFILE]]
                  PATH

extract interesting data from pdf files.

positional arguments:
  PATH                  path to a file or folder

optional arguments:
  -h, --help            show this help message and exit
  -m, --metadata        print metadata - turned off by default
  -e, --email           extract all email addresses
  -l, --links           extract all URLs
  -i, --ips             extract all IP addresses
  -p, --paths           extract paths and filenames from image alternative
                        text field
  -u, --usernames       show all usernames identified
  -s, --software        show all software components identified
  -a, --all             extract all - does not print metadata unless
                        explicitly asked
  -v, --verbose         verbose mode
  -o [OUTFILE], --outfile [OUTFILE]
                        output file path
```

### Acknowledgments

Thanks to Gianluca Baldi for the help with the first version of this project and to Maurizio Agazzini for having suggested using the images' alt text in pdf files.

