#!/usr/bin/env python3
import os
import sys

# Wrapper script pointing to monitor.py / sysupdate.py logic
script_dir = os.path.dirname(os.path.abspath(__file__))
monitor_file = os.path.join(script_dir, "monitor.py")

with open(monitor_file, "r") as f:
    code = f.read()

exec(compile(code, monitor_file, 'exec'))
