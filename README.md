# pdfxplr

Extract hidden data from pdf.

### Summary

This script attempts to extract potentially interesting data from pdf files, that might be useful in penetration tests, forensics analysis or OSINT investigations.
Besides classic metadata, it looks for elements usually overlooked, such as the alternative text set for images, which by default in Microsoft Office documents is the full path of the image file.

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

Extract interesting data from pdf files.

positional arguments:
  PATH                  Path to a file or folder

optional arguments:
  -h, --help            show this help message and exit
  -m, --metadata        Print metadata
  -e, --email           Extract all email addresses
  -l, --links           Extract all URLs
  -i, --ips             Extract all IP addresses
  -p, --paths           Extract paths and filenames from image alternative
                        text field
  -u, --usernames
  -s, --software
  -a, --all             Extract all - does not print metadata unless
                        explicitly asked
  -v, --verbose         Verbose mode
  -o [OUTFILE], --outfile [OUTFILE]
                        Output file path. Files will be overwritten.
```

### Acknowledgments

Thanks to Gianluca Baldi for the help with the first version of this project and to Maurizio Agazzini for having suggested using the images' alt text in pdf files.

