#!/bin/sh
# qnxcheck — host-side static analysis and validation toolkit for QNX 8.0.
# Runs on Linux with Python 3.10+ (stdlib only, no dependencies).
# Usage: ./qnxcheck buildfile system.build
#        ./qnxcheck c src/*.c
#        ./qnxcheck check .
#        ./qnxcheck init --target x86_64 --dir my-project
exec python3 -m qnxcheck "$@"
