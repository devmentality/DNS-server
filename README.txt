Asynchornous DNS server
Author: Volnov Nikita

Caching DNS server.
Supports A, AAAA, NS and PTR records.
Works on 127.0.0.1:53.
Uses 198.41.0.4 as root-DNS.

usage: async_main.py [-h] [--load LOAD] --save SAVE

optional arguments:
  -h, --help   show this help message and exit
  --load LOAD  name of file to load cache from
  --save SAVE  name of file to save cache in

Required: Python 3.6