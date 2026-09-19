# Part of Odoo. See LICENSE file for full copyright and licensing details.
import base64
import contextlib
import csv
import io
import logging
import re

from odoo import models
from odoo.addons.ai.models.models import AI_SUPPORTED_IMG_TYPES
from odoo.tools.pdf import OdooPdfFileReader, OdooPdfFileWriter, to_pdf_stream, PdfReadError
from odoo.tools.image import ImageProcess

_logger = logging.getLogger(__name__)


class IrAttachment(models.Model):
    _inherit = 'ir.attachment'

    AI_MAX_PDF_PAGES = 5
    TABULAR_FILE_TYPES = [
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',  # xlsx
        'application/vnd.ms-excel',  # xls
        'application/vnd.oasis.opendocument.spreadsheet',  # ods
        'text/csv',  # csv
    ]

    def _get_attachment_content(self):
        """
        Get the indexing-processed content of the attachment
        """
        self.ensure_one()
        attachment_content = ''
        if self.mimetype in self.TABULAR_FILE_TYPES:
            sheets = self.index_content.split('\n\n')
            for sheet in sheets:
                if sheet:
                    rows_list = self._process_csv_text(sheet)
                    if rows_list:
                        result = '\n'.join(str(row) for row in rows_list)
                        attachment_content += result + '\n'
        else:
            attachment_content = self.index_content

        if not attachment_content:
            return None

        # Check for reasonable content length and word variety
        if len(attachment_content.strip()) <= 10:
            return None

        unique_words = {w.lower() for w in attachment_content.split()}
        if len(unique_words) < 2:
            return None

        return attachment_content

    def _setup_attachment_chunks(self, embedding_model, content=None):
        self.ensure_one()
        # If the attachment is a tabular file, return each row as a separate chunk
        if self.mimetype in self.TABULAR_FILE_TYPES:
            chunks = content.split('\n')
        else:
            chunks = self._chunk_text(content)

        vals_list = []
        for chunk in chunks:
            if self.name:
                chunk = f"Attachment Name: {self.name}\n{chunk}"
            vals_list.append({
                'attachment_id': self.id,
                'content': chunk,
                'embedding_model': embedding_model,
            })

        self.env['ai.embedding'].create(vals_list)

    @staticmethod
    def _process_csv_text(csv_text):
        """
        Process CSV text into a list of dictionaries with headers as keys.
        :return: List of row dictionaries or None if invalid
        :rtype: list[dict] or None
        """

        lines = csv_text.strip().split('\n')
        if not lines:
            return None

        # Detect delimiter and header
        sample = '\n'.join(lines[:min(10, len(lines))])

        delimiter = ','
        has_header = False
        try:
            sniffer = csv.Sniffer()
            delimiter = sniffer.sniff(sample).delimiter
            has_header = sniffer.has_header(sample)
        except csv.Error:
            pass

        # Generate headers from first row or create generic ones
        if has_header:
            first_row = next(csv.reader(io.StringIO(lines[0]), delimiter=delimiter))
            headers = [h.strip() if h else f"Column_{i}" for i, h in enumerate(first_row)]
        else:
            first_row = next(csv.reader(io.StringIO(lines[0]), delimiter=delimiter))
            headers = [f"Column_{i}" for i in range(len(first_row))]

        # Parse CSV with safety nets for ragged rows
        reader = csv.DictReader(
            io.StringIO(csv_text),
            delimiter=delimiter,
            fieldnames=headers,
            restkey='_extra_fields',  # Extra columns to be added as extra fields key
            restval=None  # Missing columns will be added as None
        )

        if has_header:
            next(reader, None)

        rows = list(reader)
        return rows

    @staticmethod
    def _clean_text(text):
        """
        Clean up the text content while preserving meaningful structure.

        :param str text: Raw text content to clean
        :returns: Cleaned text content
        :rtype: str
        """
        # Remove NUL characters that can cause PostgreSQL insertion errors
        text = text.replace('\x00', '')
        text = text.replace('\r\n', '\n')

        # Split into lines and process
        lines = text.split('\n')
        result = []
        current_paragraph = []

        for line in lines:
            stripped = line.strip()

            if not stripped:
                if current_paragraph:
                    result.append(' '.join(current_paragraph))
                    current_paragraph = []
                continue

            if stripped.endswith(':') or (len(stripped) < 120 and stripped.endswith('.')):
                if current_paragraph:
                    result.append(' '.join(current_paragraph))
                    current_paragraph = []
                result.append(stripped)
                continue

            current_paragraph.append(stripped)

        if current_paragraph:
            result.append(' '.join(current_paragraph))

        # Join with single newlines between paragraphs
        text = '\n'.join(result)

        # Clean up extra whitespace
        text = re.sub(r'\s+', ' ', text)
        text = re.sub(r'\s+([.,!?;:])', r'\1', text)
        return text.strip()

    @staticmethod
    def _chunk_text(text, chunk_size=1500, margin=200, min_chunk_size=1000, max_chunk_size=5000):
        """
        Split text into chunks based on character count with a hard maximum limit.
        The hard max limit is 5000 characters so that the chunks have enough context for the LLM to understand in case of large chunks.

        :param str text: The input text to chunk.
        :param int chunk_size: Target chunk size in characters.
        :param int margin: Allow flexibility in chunk sizes within chunk_size ± margin.
        :param int min_chunk_size: Minimum size a chunk should have before finalizing.
        :param int max_chunk_size: Hard maximum size limit that cannot be exceeded.
        :return: List of text chunks
        :rtype: list[str]
        """
        cleaned_text = IrAttachment._clean_text(text)
        chunks = []
        paragraphs = cleaned_text.split('\n')

        current_chunk = []
        current_length = 0

        def _add_chunk_enforcing_max_size(chunk_content):
            """Add a chunk, splitting it if it exceeds max_chunk_size."""
            if len(chunk_content) <= max_chunk_size:
                chunks.append(chunk_content)
            else:
                # Force split oversized chunks by words
                words = chunk_content.split()
                temp_chunk = []
                temp_length = 0
                for word in words:
                    word_length = len(word) + 1
                    if temp_length + word_length > max_chunk_size:
                        if temp_chunk:
                            chunks.append(" ".join(temp_chunk))
                        temp_chunk = [word]
                        temp_length = len(word)
                    else:
                        temp_chunk.append(word)
                        temp_length += word_length
                if temp_chunk:
                    chunks.append(" ".join(temp_chunk))

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue  # Skip empty lines

            para_length = len(para)

            # If current chunk is too small, try to merge with the next one
            if current_chunk and (current_length + para_length + 1 <= chunk_size + margin):
                current_chunk.append(para)
                current_length += para_length + 1
                continue

            # If the current chunk is large enough, store it
            if current_length >= chunk_size - margin:
                _add_chunk_enforcing_max_size(" ".join(current_chunk))
                current_chunk = [para]  # Start a new chunk
                current_length = para_length
            else:
                # If chunk is too small but para itself is too big, split it
                if para_length > chunk_size:
                    # First, store current chunk if it exists
                    if current_chunk:
                        _add_chunk_enforcing_max_size(" ".join(current_chunk))
                        current_chunk = []
                        current_length = 0
                    # Split the large paragraph by sentences
                    sentences = re.split(r'(?<=[.!?])\s+', para)
                    temp_chunk = []
                    temp_length = 0

                    for sentence in sentences:
                        sent_length = len(sentence)

                        if temp_length + sent_length + 1 > chunk_size:
                            if temp_chunk:
                                _add_chunk_enforcing_max_size(" ".join(temp_chunk))
                            temp_chunk = [sentence]
                            temp_length = sent_length
                        else:
                            temp_chunk.append(sentence)
                            temp_length += sent_length + 1

                    if temp_chunk:
                        _add_chunk_enforcing_max_size(" ".join(temp_chunk))
                else:
                    current_chunk.append(para)
                    current_length += para_length + 1

        # Handle the last chunk
        if current_chunk:
            last_chunk_content = " ".join(current_chunk)
            if chunks and len(last_chunk_content) < min_chunk_size:
                # Try to merge with the previous chunk, but respect max_chunk_size
                if len(chunks[-1]) + len(last_chunk_content) + 1 <= max_chunk_size:
                    chunks[-1] += " " + last_chunk_content
                else:
                    # Can't merge, add as separate chunk
                    _add_chunk_enforcing_max_size(last_chunk_content)
            else:
                _add_chunk_enforcing_max_size(last_chunk_content)

        return chunks

    def _ai_read(self, fnames, files_dict):
        """When attachments are inserted in a prompt, one send the files (or indexed contents) to
        the LLMs.
        """
        if fnames:
            return super()._ai_read(fnames, files_dict)
        vals = []
        for attachment in self:
            if attachment.checksum in files_dict:
                vals.append({'id': attachment.id, 'file': files_dict[attachment.checksum]['file_ref']})
                continue
            file_ref = f'<file_#{len(files_dict) + 1}>'
            extension = attachment.mimetype.split('/')[-1]
            if extension == 'pdf' and not attachment.url:
                # Extract the X first / last pages of the PDFs
                reader = None
                with contextlib.suppress(PdfReadError):
                    reader = OdooPdfFileReader(to_pdf_stream(attachment), strict=False)
                if not reader or reader.numPages <= self.AI_MAX_PDF_PAGES:
                    b64_datas = attachment.datas.decode()
                else:
                    writer = OdooPdfFileWriter()
                    start_pages = self.AI_MAX_PDF_PAGES // 2
                    end_pages = self.AI_MAX_PDF_PAGES - start_pages
                    for p in (*range(start_pages), *range(reader.numPages - end_pages, reader.numPages)):
                        writer.addPage(reader.getPage(p))
                    out_buff = io.BytesIO()
                    writer.write(out_buff)
                    b64_datas = base64.b64encode(out_buff.getvalue()).decode()

                files_dict[attachment.checksum] = {
                    'mimetype': 'application/pdf',
                    'value': b64_datas,
                    'file_ref': file_ref,
                }
            elif extension in AI_SUPPORTED_IMG_TYPES and not attachment.url:
                raw_data = attachment.raw

                try:
                    image_process = ImageProcess(raw_data)
                    size = image_process.image.size
                    if max(size) > 1024:
                        raw_data = image_process \
                            .crop_resize(min(size[0], 1024), min(size[1], 1024), 0, 0) \
                            .image_quality(output_format='PNG')
                except Exception as e:  # noqa: BLE001
                    _logger.error("Image resize failed %s", e)

                files_dict[attachment.checksum] = {
                    'mimetype': attachment.mimetype,
                    'value': base64.b64encode(raw_data).decode(),
                    'file_ref': file_ref,
                }
            else:
                if not attachment.index_content or attachment.index_content == "application":
                    continue
                files_dict[attachment.checksum] = {
                    'mimetype': 'text/plain',
                    'value': attachment.index_content,
                    'file_ref': file_ref
                }
            vals.append({'id': attachment.id, 'file': file_ref})
        return vals, files_dict
