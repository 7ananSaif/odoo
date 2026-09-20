# Part of Odoo. See LICENSE file for full copyright and licensing details.
import re


# Matches AI citation tokens such as [SOURCE:210] or [SOURCE:210, 211]
CITATION_REGEX = re.compile(r"""
    \[SOURCE:
        ([0-9]+
            (?:\s*,\s*[0-9]+)*
        )
    \]
""", re.VERBOSE)


def get_attachment_ids_from_text(text):
    """
    Return unique attachment ids from inline AI citation tags in the provided text.
    """
    if not text:
        return []
    sources = CITATION_REGEX.findall(text)
    attachment_ids = [int(id.strip()) for source in sources for id in source.split(',')]
    unique_attachment_ids = list(set(attachment_ids))
    return unique_attachment_ids


def apply_numeric_citations(text, attachment_data, link_attrs='target="_blank" rel="noreferrer noopener"'):
    """
    Replace inline citations with numbered, clickable citations [1][2]...
    :param text: The input text containing citation placeholders (e.g., [SOURCE:ID1, ID2, ...])
    :param attachment_data: Map of attachment_id -> {'url', 'source_name'}
    :param link_attrs: HTML attributes for the citation link
    :return: new_content
    :rtype: str
    """
    if not text:
        return ""

    new_content = ""
    text_pieces = CITATION_REGEX.split(text)
    resolved_citations = {}
    for index, text_piece in enumerate(text_pieces):
        if index % 2 == 0:
            new_content += text_piece.rstrip(" ")
        else:
            attachment_ids = text_piece.split(',')
            for attachment_id in attachment_ids:
                attachment_id_int = int(attachment_id.strip())
                attachment_info = attachment_data.get(attachment_id_int, {})
                if not attachment_info:
                    continue
                href = attachment_info['url']
                if attachment_id_int not in resolved_citations:
                    citation_num = len(resolved_citations) + 1
                    resolved_citations[attachment_id_int] = citation_num
                else:
                    citation_num = resolved_citations[attachment_id_int]
                citation_html = f'<sup><a href="{href}" {link_attrs} style="text-decoration: none;"> [{citation_num}] </a></sup>'
                new_content += citation_html

    return new_content
