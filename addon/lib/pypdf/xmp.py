"""
Minimal XMP compatibility shim for PDF para Audiolivro.

The add-on only extracts page text and never reads or writes XMP metadata.
pypdf imports XmpInformation while defining PdfReader, so this lightweight
class avoids pulling xml.dom / xml.parsers into NVDA's frozen runtime.
"""

class XmpInformation:
    def __init__(self, stream):
        self.stream = stream

    def write_to_stream(self, stream, encryption_key=None):
        data = getattr(self.stream, "get_data", None)
        if callable(data):
            payload = data()
            if payload:
                stream.write(payload)
