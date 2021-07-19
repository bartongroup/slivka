#!/usr/bin/env python3

# usage: example.py [--infile FILE] [--opt TEXT]
#   [--rep REP[,REP,...]] [--delay SECONDS] [--letter LETTER] [--flag] -- arg

import argparse
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--infile', metavar='FILE')
parser.add_argument('--opt', metavar='TEXT')
parser.add_argument('--rep', )
parser.add_argument('--delay', metavar='SECONDS', type=int, default=0)
parser.add_argument('--letter', metavar='LETTER', choices='ABCD')
parser.add_argument('--flag', action='store_true')
parser.add_argument('arg')
args = parser.parse_args()

line = "\n"
if args.infile:
    print(f"reading from file {args.infile}")
    try:
        line = next(open(args.infile))
    except StopIteration:
        print("Input file is empty", file=sys.stderr)
with open('output.txt', 'w') as f:
    f.write(line)

if args.opt:
    print(f"opt is {args.opt}")
rep = args.rep.split(',') if args.rep else []
print(f"rep is repeated {len(rep)} times.")
for i, val in enumerate(rep):
    with open(f"rep.{i}.txt", 'w') as f:
        f.write(f"{val}\n")
if args.letter:
    print(f"letter is {args.letter}")
print(f"flag is {'present' if args.flag else 'absent'}")
print(f"last argument is {args.arg}")
if args.delay > 0:
    time.sleep(args.delay)
