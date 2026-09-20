import re

from lxml import etree
from lxml.etree import XMLSyntaxError

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError

DEFAULT_ADDENDA_ARCH = '''\
<t>
    <t t-xml-node="comprobante">  <!-- this node is optional -->
        <!-- Define the namespaces/schema locations to be injected to Comprobante here -->
        <t t-namespace-key="abcd" t-namespace-url="http://www.sat.gob.mx/abcd/"/>
        <t t-schema-locations="https://www.schema_url_1.com/ https://www.schema_url_2.com/"/>
    </t>
    <t t-xml-node="addenda">  <!-- this node is required. accepted values: "addenda", "complemento" -->
        <!-- Define your addenda/complementos here -->
        <abcd:Test>Hello, World!</abcd:Test>
    </t>
</t>
'''

# Regex patterns to match custom XML containing additional information needed for the addenda
XML_DECLARATION_PATTERN = r"<\?xml version=['\"]1.0['\"]\?>"
XML_COMMENT_PATTERN = r"<\!--.*-->"
ADDENDA_NAMESPACES_PATTERN = r'<t t-namespace-key=["\'](.*?)["\'] t-namespace-url=["\'](.*?)["\']\/>'
ADDENDA_SCHEMA_LOCATIONS_PATTERN = r"<t t-schema-locations=['\"](.*?)['\"]\/>"


class L10n_Mx_EdiAddenda(models.Model):
    _name = 'l10n_mx_edi.addenda'
    _description = 'Addenda for Mexican EDI'

    name = fields.Char(string='Name', required=True)
    arch = fields.Text(
        string='Architecture',
        required=True,
        default=DEFAULT_ADDENDA_ARCH,
    )

    @api.model
    def _get_all_namespaces_from_xml(self, xml_str: str) -> dict[str, str]:
        nsmap = {}
        matches = re.findall(ADDENDA_NAMESPACES_PATTERN, xml_str)
        for key, url in matches:
            nsmap[key] = url
        return nsmap

    @api.model
    def _get_schema_locations_from_xml(self, xml_str: str) -> str:
        match = re.search(ADDENDA_SCHEMA_LOCATIONS_PATTERN, xml_str)
        if match:
            return match.group(1).strip()
        return ""

    @api.model
    def _wrap_xml_with_namespaces(self, xml_str: str, nsmap: dict) -> str:
        wrapped_xml_list = [
            '<t',
            *[f' xmlns:{key}="{url}"' for (key, url) in nsmap.items()],
            '>\n',
            xml_str,
            '\n</t>',
        ]
        wrapped_xml = ''.join(wrapped_xml_list)
        return wrapped_xml

    @api.model
    def _get_cleaned_addenda_xml(self, xml_str: str, clean_custom_xml=False) -> str:
        """
        Gets the arch of the addenda with some adjustments:
        - Removes the XML declaration / comment string if it exists
        - Removes all custom addenda additional information in the <t> nodes if they exist
        - Strips any unneeded whitespace
        """
        res_arch = xml_str
        res_arch = re.sub(XML_DECLARATION_PATTERN, '', res_arch or '')
        res_arch = re.sub(XML_COMMENT_PATTERN, '', res_arch or '')
        if clean_custom_xml:
            res_arch = re.sub(ADDENDA_NAMESPACES_PATTERN, '', res_arch or '')
            res_arch = re.sub(ADDENDA_SCHEMA_LOCATIONS_PATTERN, '', res_arch or '')
        res_arch = res_arch.strip()
        return res_arch

    @api.model
    def _get_decoded_xml_node(self, decoded_data: dict) -> str:
        for decoded_key in decoded_data:
            if decoded_key in ('complemento', 'addenda'):
                return decoded_key

        # if `decoded_data` in the parameter is not valid, return 'addenda' by default
        return 'addenda'

    def _decode_single_addenda_arch(self) -> dict[str, str] | dict[str, dict]:
        """
        --- Format of returned dictionary ---
        If the decode process failed:
            {
                'error': <error_str>,
            }
        If the decode process succeeded:
            {
                <optional> 'comprobante' : {'nsmap': <namespaces_dict>, 'schema_locations': <schema_locations_str>},
                <required>  <xml_node>   : {'nsmap': <namespaces_dict>, 'arch': <xml_arch_str>},
            }
        (where "<xml_node>" can be either "addenda" or "complemento".)
        """
        self.ensure_one()
        cleaned_arch = self._get_cleaned_addenda_xml(self.arch)
        nsmap = self._get_all_namespaces_from_xml(cleaned_arch)
        wrapped_xml = self._wrap_xml_with_namespaces(cleaned_arch, nsmap)
        full_arch_element = etree.fromstring(wrapped_xml)
        xml_node_elements = full_arch_element.getchildren()
        error_message = ""

        # if the user manually wrapped everything in a single or more <t> element, unwrap it
        while len(xml_node_elements) == 1 and xml_node_elements[0].tag == 't' and xml_node_elements[0].attrib == {}:
            xml_node_elements = xml_node_elements[0].getchildren()

        decoded_data: dict[str, dict] = {}

        for element in xml_node_elements:
            if element.tag != 't' or 't-xml-node' not in element.attrib:
                error_message = _("Arch must contain `<t t-xml-node=\"(addenda_type)\">(your addenda here)</t>`, "
                                  "where addenda_type is either 'complemento' or 'addenda'")
                break
            if element.attrib['t-xml-node'] not in ('comprobante', 'complemento', 'addenda'):
                error_message = _("Arch value of t-xml-node must be either 'comprobante', 'complemento', or 'addenda'")
                break

            element_str = etree.tostring(element).decode()
            xml_node = element.attrib['t-xml-node']
            decoded_data[xml_node] = {}
            decoded_data[xml_node]['nsmap'] = self._get_all_namespaces_from_xml(element_str)

            if xml_node == 'comprobante' and (schema_locations := self._get_schema_locations_from_xml(element_str)):
                if '' in schema_locations.split(' '):
                    error_message = _("Schema locations must be separated by only one whitespace character.")
                    break
                decoded_data['comprobante']['schema_locations'] = schema_locations
            else:  # complemento / addenda
                if 'arch' not in decoded_data[xml_node]:
                    decoded_data[xml_node]['arch'] = ""
                for core_elements in element.getchildren():
                    decoded_data[xml_node]['arch'] += self._get_cleaned_addenda_xml(etree.tostring(core_elements).decode(), clean_custom_xml=True)

        if not error_message and not (('complemento' in decoded_data) ^ ('addenda' in decoded_data)):
            # True if both complemento & addenda exist, or both doesn't exist.
            error_message = _("Arch must contain either complemento or addenda (but not both at the same time)")

        if error_message:
            return {'error': error_message}

        return decoded_data

    def _decode_multi_addenda_arch(self) -> dict[str, list[str]] | dict[str, dict]:
        """
        --- Format of returned dictionary ---
        If any of the addenda failed the decoding process:
        {
            'errors': <error_list[str]>,
        }
        If all the addenda succeeded the decoding process:
        {
            'comprobante' : {'nsmap': <namespaces_dict>, 'schema_locations': <schema_locations_str>},
             <xml_node>   : {'nsmap': <namespaces_dict>, 'arch': <xml_arch_str>},
        }
        (where "<xml_node>" can be either "addenda" or "complemento".)
        """
        seen_xml_node = set()
        final_nsmap = {}
        final_arch_nsmap = {}
        arch_list = ["<t>"]
        schema_list = []
        errors = []

        for addenda in self:
            decoded_data = addenda._decode_single_addenda_arch()
            if 'error' in decoded_data:
                errors.append(f"[addenda={addenda.id}] {decoded_data['error']}")
                continue

            xml_node = self._get_decoded_xml_node(decoded_data)
            seen_xml_node.add(xml_node)
            if len(seen_xml_node) == 2:
                # Do not process the decode result if the function are called without a filtered recordset.
                errors = [_("Both addenda and complementos are detected in the recordset.")]
                break

            final_arch_nsmap.update(decoded_data[xml_node]['nsmap'])
            arch_list.append(decoded_data[xml_node]['arch'])

            if 'comprobante' in decoded_data:
                final_nsmap.update(decoded_data['comprobante']['nsmap'])
                if schema_locations := decoded_data['comprobante']['schema_locations']:
                    schema_list.append(schema_locations)

        if not errors and not seen_xml_node:
            # In case `self` is empty, add an error to prevent error raised from `seen_xml_node.pop()`
            errors.append(_("No addenda or complementos were successfully processed from the recordset."))
        if errors:
            return {'errors': errors}

        arch_list.append("</t>")
        final_arch_xml = "".join(arch_list).strip()
        final_schema_locations = ' '.join(sorted(set(schema_list)))
        xml_node = seen_xml_node.pop()

        return {
            'comprobante': {
                'nsmap': final_nsmap,
                'schema_locations': final_schema_locations,
            },
            xml_node: {
                'nsmap': final_arch_nsmap,
                'arch': final_arch_xml,
            },
        }

    def _filter_addenda_by_xml_node(self, xml_node: str):
        """
        :param xml_node: "addenda" or "complemento"
        """
        selected_addenda = self.env['l10n_mx_edi.addenda']

        if xml_node not in ('addenda', 'complemento'):
            # if xml_node parameter is invalid, return empty addenda record by default
            return selected_addenda

        for addenda in self:
            decoded_data = addenda._decode_single_addenda_arch()
            if 'error' in decoded_data:
                continue

            decoded_xml_node = self._get_decoded_xml_node(decoded_data)
            if decoded_xml_node == xml_node:
                selected_addenda |= addenda

        return selected_addenda

    @api.constrains('arch')
    def _validate_xml(self):
        for addenda in self:
            if addenda_arch := self._get_cleaned_addenda_xml(addenda.arch):
                try:
                    nsmap = self._get_all_namespaces_from_xml(addenda_arch)
                    test_arch = self._wrap_xml_with_namespaces(addenda_arch, nsmap)
                    etree.fromstring(test_arch)
                except XMLSyntaxError as e:
                    raise ValidationError(_('Invalid addenda definition:\n %s', e)) from e

            decoded_data = addenda._decode_single_addenda_arch()
            if 'error' in decoded_data:
                raise ValidationError(_("Decoding of addenda XML arch failed:\n%s", decoded_data['error']))
