import xml.etree.ElementTree as ET
import re
from dataclasses import dataclass, field
from typing import Dict, Union


@dataclass
class FormField:
    section:        str = None
    field_name:     str = None  # The field name contained in the XML tag
    name:           str = None  # The human-readable field name derived from the caption or tooltip
    name_tag:       str = None
    items:          Dict[str, str] = field(default_factory=lambda: {}) # For storage of dropdown list items
    value:          str = None


@dataclass
class FormObject:
    type:           str = None
    fields:         Dict[str, FormField] = field(default_factory=lambda: {})


@dataclass
class DoclevelObjects:
    attachments:    Dict[str, Dict[str, Union[str, bytes]]] = field(default_factory=lambda: {})
    form:           FormObject = None


class GetDoclevelObjects(DoclevelObjects):
    """Extracts attachments and form data from a PDF

        Parameters
        ----------

        pdf : pypdf.PdfReader object
            The PDF file in question

        Returns
        -------

        attachments: Dict

        form: FormObject
    """
    def __init__(self, pdf):
        catalog = pdf.trailer["/Root"]
        self.attachments = self.get_attachments(catalog)
        self.form = FormObject()
        if '/AcroForm' in catalog.keys():
            if not len(pdf.xfa):
                self.form.type = 'AcroForm'
                self.form.fields = self.process_acroform(pdf)
            else:
                xfa = XFAHandler(pdf)
                self.form.type = xfa.type
                self.form.fields = xfa.fields

    def get_attachments(self, catalog):
        """Read embedded files from PDF

        Embedded file metadata is stored in a dictionary:
        {
            '/Desc': Content description (optional),
             '/EF':
                {
                    '/F': PDF IndirectObject reference to file bytes
                },
             '/F': Filename,
             '/Type': '/Filespec',
             '/UF': Some other data (filename?)
         }


        Parameters
        ----------

        catalog : PDF catalog
            The PDF file in question

        Returns
        -------

        result: dict
            A dictionary with the following structure:
            {
                filename:
                    {
                        'desc': file description,
                        'file_bytes': a bytestream of the attachment
                    }
            }
        """
        result = {}
        # Check if there are any embedded files
        if '/Names' in catalog.keys() and '/EmbeddedFiles' in catalog['/Names'].keys():
            embeds = catalog['/Names']['/EmbeddedFiles']
            # Sometimes there's an /EmbeddedFiles object even when there are none
            if '/Names' not in embeds.keys():
                attachments = []
            else:
                attachments = [x for n, x in enumerate(embeds['/Names']) if n % 2 == 1]
            # See comments above for a description of the contents of the embedded files list
            for item in attachments:
                filespec = item.get_object()
                fn = filespec['/F']
                file_bytes = filespec['/EF']['/F'].get_data()
                desc = fn if '/Desc' not in filespec.keys() else filespec['/Desc']
                result[fn] = {'desc': desc, 'file_bytes': file_bytes}
        return result

    def process_acroform(self, pdf):
        result = {}
        for key, val in pdf.get_fields().items():
            result[key] = FormField(field_name=key,
                                    name=val['/T'],
                                    value=None if '/V' not in val.keys() else val['/V'])
        return result


class XFAHandler(FormObject):
    """Read data from XFA objects

    Parameters
    ----------

    acroform : pypdf.PdfReader object
        The PDF file in question

    Returns
    -------

        _xml_root: xml.etree.ElementTree
        _namespaces: Dict
        type: String
        fields: FormData
    """

    def __init__(self, pdf):
        xfa = pdf.xfa
        self._xml_root = self.get_xfa_xml(xfa)
        self._namespaces = self.get_namespaces()
        self.type = 'XFA'
        self.fields = self.get_fields_from_template()
        self.get_fields_from_dataset()

    def get_xfa_xml(self, xfa):
        """Converts XFA XML embedded in a PDF to an XML root object

        Parameters
        ----------

        xfa : pypdf.PdfReader.xfa object

        Returns
        -------

        root : xml.etree.ElementTree
        """
        # The Adobe XFA XML is contained in a list in which the XML is only in the odd-numbered
        # list elements
        objs = [i.decode() for i in xfa.values()]
        xstr = "".join(objs)
        root = ET.fromstring(xstr)
        return root

    def get_namespaces(self):
        """Extracts list of namespaces from the XFA XML root

        Returns
        -------

        namespaces : Dict of namespaces
            descr
        """
        namespaces = {}
        for elem in list(self._xml_root):
            ns, tag = re.match(r'\{(.+)\}(.+)', elem.tag).groups()
            namespaces[tag] = ns
        return namespaces

    def get_fields_from_template(self, elem=None, result=None, parent=None):
        """Recursive function that parses a template namespace tree from an XFA document

        Extracts all necessary child elements (presently forms, subforms, and fields) and tracks
        tag parent names so that a section name can be constructed out of a dot-separated list of
        tag names

        Parameters
        ----------

        elem : type
            descr
        result : Dict
            See below - included as a parameter for recursion
        parent : String
            Dot-separated list of the tag names of the current element's ancestors

        Returns
        -------

        result : Dict
            {element name: FormField}
            The name_tag field is probably superfluous, and it's being used to hold attachment
            metadata, which will probably be ultimately unnecessary
        """
        # Initialize result dict
        result = {} if result is None else result

        # Begin at the template root element
        elem = elem if elem is not None else self._xml_root.find(".//template:template", self._namespaces)

        # Remove namespace from tag name
        tag_name = elem.tag.split("}")[-1]

        # Extract element name, if present
        elem_name = tag_name if "name" not in elem.attrib.keys() else elem.attrib["name"]

        if (
                tag_name == "subform"
        ):  # if tag is a subform save its name as the parent for subsequent iterations
            parent = (
                None
                if elem_name == "root"
                else elem_name
                if parent is None
                else f"{parent}.{elem_name}"
            )
        elif tag_name == "field":  # if the tag is a field tag...
            # exclude uninteresting element types
            # TODO: include only interesting element types instead of excluding
            if (not re.search("delete", elem_name.lower())
                    and not re.search("example", elem_name.lower())
                    and not re.search("tips", elem_name.lower())
            ):
                # This section will need to be ripped out and moved to the eSTAR wrapper
                if re.search("addattachment", elem_name.lower()):
                    tag = 'script'
                    cur = elem.find(f".//template:{tag}", self._namespaces)
                    try:
                        cur = re.sub('[\n\r]+', '', cur.text)
                        name = re.match(r'.+\[AttachmentIndex\]\.path \+ "(.+?)"', cur).groups()[0]
                        name_tag = re.match(r'.+\[AttachmentIndex\]\.description \= "(.+?)"', cur).groups()[0]
                    except:
                        print(tag_name, elem_name)
                        print(cur)
                        raise

                else:
                    name = ""
                    name_tag = ""
                    # There are two tags (caption and toolTip) where the script looks for a
                    # descriptive field name
                    # This logic might be (probably is) eSTAR-specific as well
                    name_tags = [
                        "caption",
                        "toolTip",
                    ]
                    for tag in name_tags:
                        cur = elem.find(f".//template:{tag}", self._namespaces)
                        if cur is not None:
                            if not len(
                                    name
                            ):  # pull the field name and text from the element text...unless the
                                # field name was already found in the other tag type
                                name = "".join(cur.itertext())
                                name_tag = tag

                # save field metadata to dictionary
                if len(name):
                    result[elem_name] = FormField(section=parent,
                                                  field_name=elem_name,
                                                  name=name,
                                                  name_tag=name_tag)

                    # parse dropdown list values, if necessary
                    items = elem.findall(".//template:items", self._namespaces)
                    if len(items) == 2:
                        result[elem_name].items = dict(
                            zip(list(items[1].itertext()), list(items[0].itertext()))
                        )

        # see if there are subelements and recurse into them if necessary
        subs = elem.findall("*", self._namespaces)
        if len(subs):
            for item in subs:
                result = self.get_fields_from_template(item, result, parent)
        return result

    def get_fields_from_dataset(self):
        """Reads the field list generated by get_fields_from_template(), finds each of the
        fields in the dataset namespace, and extracts the field value
        """
        # Find the root XML for the datasets namespace
        datasets = self._xml_root.find(".//datasets:datasets", self._namespaces)

        for field_name, field in self.fields.items():
            # Loop through each field found in the template and find all instances of it in the
            # datasets namespace.
            elem = datasets.findall(f".//{field_name}")
            if elem is not None:
                # Unproven assumption: All form elements that have a value assigned to them will
                # have content in the text attribute.
                for item in elem:
                    # Use item.text as the field value if the field is a dropdown list and the
                    # text is not in the list, otherwise use the dropdown value
                    if item.text is not None:
                        if len(self.fields[field_name].items):
                            val = (
                                item.text
                                if item.text not in self.fields[field_name].items.keys()
                                else self.fields[field_name].items[item.text]
                            )
                        else:
                            val = item.text
                        # If there are multiple values for a field append each new value for that
                        # field to a list, otherwise set the field value to whatever was determined
                        # above.
                        if self.fields[field_name].value is not None and len(self.fields[field_name].value):
                            if not isinstance(self.fields[field_name].value, list):
                                self.fields[field_name].value = [self.fields[field_name].value]
                            self.fields[field_name].value.append(val)
                        else:
                            self.fields[field_name].value = val