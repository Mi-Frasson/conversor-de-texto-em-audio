"""
Subset of pypdf bundled for PDF text extraction in PDF para Audiolivro.
Only PdfReader is exported to reduce dependencies in NVDA's frozen Python.
"""

from ._reader import PdfReader
from ._version import __version__

__all__ = ["PdfReader", "__version__"]
