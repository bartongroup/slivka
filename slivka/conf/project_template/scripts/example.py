#!/usr/bin/env python3

import sys
import time
from argparse import ArgumentParser

parser = ArgumentParser()
parser.add_argument('-v', action='store_true')
parser.add_argument('--infile')
parser.add_argument('-t', '--text')
parser.add_argument('-r', '--repeat', type=int, default=0)
parser.add_argument('-w', '--sleep', type=float, default=0)
parser.add_argument('--log', action='store_true')
parser.add_argument('outfile')
args = parser.parse_args()

if args.v: print('I\'m verbose\n')

try:
    with open(args.infile or '.') as f:
        print(f.read())
except OSError:
    print('Could not open input file', file=sys.stderr)

with open(args.outfile, 'w') as f:
    print(args.text, file=f)

if args.log: print('Some log', file=sys.stderr)

for i in range(1, args.repeat + 1):
    with open('extra-output.%d.json' % i, 'w') as f:
        print('{"hello": "world"}', file=f)

time.sleep(args.sleep)
