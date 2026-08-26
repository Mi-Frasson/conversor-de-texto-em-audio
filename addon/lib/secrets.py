# -*- coding: utf-8 -*-
"""Minimal compatibility implementation for frozen NVDA Python.

This add-on only needs token_bytes(), which pypdf uses for PDF encryption
helpers. It is implemented with os.urandom, the same OS-backed source of
cryptographically secure random bytes used by Python's standard library.
"""
import os

def token_bytes(nbytes=None):
    if nbytes is None:
        nbytes = 32
    return os.urandom(nbytes)
