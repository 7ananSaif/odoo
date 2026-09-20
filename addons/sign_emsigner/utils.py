# Part of Odoo. See LICENSE file for full copyright and licensing details.

import base64
import lzma


def compress_pdf_base64(pdf_data):
    """ Compress the PDF data using LZMA and encode it to base64

    :param pdf_data: PDF file data to compress
    :return: Compressed bytes data
    """
    # Compress using LZMA
    compressed_data = lzma.compress(pdf_data, format=lzma.FORMAT_ALONE)

    return compressed_data


def decompress_pdf_base64(compressed_base64):
    """ Decompress the LZMA compressed base64 PDF data """
    # Decode base64 input string to bytes
    compressed_data = base64.b64decode(compressed_base64)
    decompressed_data = lzma.decompress(compressed_data, format=lzma.FORMAT_ALONE)

    # Return decompressed PDF data as base64
    return base64.b64encode(decompressed_data).decode('utf-8')
