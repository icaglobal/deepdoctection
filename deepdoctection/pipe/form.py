from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1, PDFObjRef
import xml.etree.ElementTree as ET
import re


class FormHandler:
    """Reads PDF forms (both XFA and AcroForm)

    Uses PDFMiner to parse the PDF passing the file to the `XFAHandler` or  `AcroFormHandler`
    classes as necessary to p[rocess the form data.

    Given that PDFs without forms can have embedded files it's likely that the  `get_attachments`
    function will be moved elsewhere or this class will be expanded to cover not just forms, but
    all data structures embedded in a PDF. But today is not that day...

    The returned `data` dictionary currently holds two values:
        t_fields : a list of all fields present in the form
                    (initially developed in the XFA context...it may not be relevant for AcroForms
                    and may be removed entirely)
        cell_values : a dictionary of all fields and values present in the form

    Parameters
    ----------

    pdf : pypdf.PdfReader
        The PDF file in question

    Returns
    -------
    _doc : pdfminer.pdfdocument.PDFDocument
        The parsed PDFDocument
    _catalog : pdfminer.pdfdocument.PDFDocument.catalog
        The resolved document catalog object
    formtype : string
        One of 'AcroForm', 'XFA', or None
    data : dict
        The fields found on the form.
    attachments : dict
        All embedded attachments found in the form (see `get_attachments` for more details)
    """

    def __init__(self, pdf):
        pdf_bytes = pdf.stream.raw
        parser = PDFParser(pdf_bytes)
        doc = PDFDocument(parser)
        catalog = resolve1(doc.catalog)
        self._doc = doc
        self._catalog = catalog

        self.formtype = None
        self.data = None
        self.attachments = self.get_attachments(pdf)

        # All forms, whether AcroForm or XFA, are contained in the 'AcroForm' element of the catalog
        if 'AcroForm' in catalog.keys():
            acroform = resolve1(catalog['AcroForm'])
            # But only XFA data is contained in the 'XFA' subelement
            if 'XFA' in acroform.keys():
                self.formtype = 'XFA'
                form = XFAHandler(acroform)
                self.data = form.data
            # The 'Fields' subelement holds AcroForm field data, if there is one
            elif 'Fields' in acroform.keys() and isinstance(acroform['Fields'], PDFObjRef):
                self.formtype = 'AcroForm'
                form = AcroFormHandler(pdf)
                self.data = form.data

    def get_attachments(self, pdf):
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

        pdf : pypdf.PdfReader object
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
        pdf_root = pdf.trailer['/Root']
        # Check if there are any embedded files
        if '/Names' in pdf_root.keys() and '/EmbeddedFiles' in pdf_root['/Names'].keys():
            embeds = pdf_root['/Names']['/EmbeddedFiles']
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


class AcroFormHandler:
    """Read data from AcroForm objects

    Parameters
    ----------

    pdf : pypdf.PdfReader object
        The PDF file in question

    Returns
    -------

    result: dict
        A dictionary with the following structure:
            {
                't_fields': List of all fields in template,
                'cell_values': A key : value listing of all fields in the form, both with and without data
            }
    """

    def __init__(self, pdf):
        self.data = self.process_acroform(pdf)

    def process_acroform(self, pdf):
        fields = pdf.get_fields()
        t_fields = {}
        for key, val in fields.items():
            t_fields[key] = {
                "section": None,
                "field_name": key,
                "name": val['/T'],
                "name_tag": None,
            }

        result = {
            't_fields': t_fields,
            "cell_values": {v['/T']:None if '/V' not in v.keys() else v['/V'] for v in fields.values()},
        }
        return result


class XFAHandler:
    """Read data from XFA objects

    Parameters
    ----------

    acroform : pdfminer.pdfdocument.PDFDocument.catalog['AcroForm'] object
        The AcroForm element of the PDF file in question

    Returns
    -------

    result: dict
        A dictionary with the following structure:
            {
                't_fields': List of all fields in template,
                'cell_values': key : value listing of all fields in the form
            }
    """

    def __init__(self, acroform):
        xfa = resolve1(acroform["XFA"])
        self.xml_root = self.get_xfa_xml(xfa)
        self.namespaces = self.get_namespaces()
        self.data = None
        self.data = self.process_xfa()

    def get_xfa_xml(self, xfa):
        """Converts XFA XML embedded in a PDF to an XML root object

        Parameters
        ----------

        xfa : Resolved pdfminer.pdfdocument.PDFDocument.catalog['AcroForm']['XFA'] object

        Returns
        -------

        root : xml.etree.ElementTree
        """
        # The Adobe XFA XML is contained in a list in which the XML is only in the odd-numbered
        # list elements
        objs = [resolve1(x).get_data().decode() for n, x in enumerate(xfa) if n % 2 == 1]
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
        for elem in list(self.xml_root):
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
            {element name:
                {
                    "section": Dot-separated list of the tag names of the element's ancestors,
                    "field_name": xml.etree.ElementTree.Element.attrib['name'],
                    "name": Long descriptive name of field taken from caption or toolTip tags,
                    "name_tag": The name of the tag where the fieldname was gathered,
                    "items": Items found in a dropdown list (if the fields is a dropdown),
                }
            }
            The name_tag field is probably superfluous, and it's being used to hold attachment
            metadata, which will probably be ultimately unnecessary
        """
        # Initialize result dict
        result = {} if result is None else result

        # Begin at the template root element
        elem = elem if elem is not None else self.xml_root.find(".//template:template", self.namespaces)

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
                    cur = elem.find(f".//template:{tag}", self.namespaces)
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
                    # There are two tags (caption and toolTip) where the script looks for a
                    # descriptive field name
                    # This logic might be (probably is) eSTAR-specific as well
                    name_tags = [
                        "caption",
                        "toolTip",
                    ]
                    for tag in name_tags:
                        cur = elem.find(f".//template:{tag}", self.namespaces)
                        if cur is not None:
                            if not len(
                                    name
                            ):  # pull the field name and text from the element text...unless the
                                # field name was already found in the other tag type
                                name = "".join(cur.itertext())
                                name_tag = tag

                # save field metadata to dictionary
                if len(name):
                    result[elem_name] = {
                        "section": parent,
                        "field_name": elem_name,
                        "name": name,
                        "name_tag": name_tag,
                    }
                    # parse dropdown list values, if necessary
                    items = elem.findall(".//template:items", self.namespaces)
                    if len(items) == 2:
                        result[elem_name]["items"] = dict(
                            zip(list(items[1].itertext()), list(items[0].itertext()))
                        )

        # see if there are subelements and recurse into them if necessary
        subs = elem.findall("*", self.namespaces)
        if len(subs):
            for item in subs:
                result = self.get_fields_from_template(item, result, parent)
        return result

    def get_fields_from_dataset(self, fields):
        """Reads the field list generated by get_fields_from_template(), finds each of the
        fields in the dataset namespace, and extracts the field value

        Parameters
        ----------

        fields : dict
            Output from self.get_fields_from_template()

        Returns
        -------

        fields : dict
            The input dictionary is simply modified by this function. If I'm going to do that
            I should probably just make fields a class object so it doesn't have to be passed
            around.
        """
        # Find the root XML for the datasets namespace
        datasets = self.xml_root.find(".//datasets:datasets", self.namespaces)

        for field_name, field in fields.items():
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
                        if "items" in fields[field_name].keys() and len(
                                fields[field_name]["items"].keys()
                        ):
                            val = (
                                item.text
                                if item.text not in fields[field_name]["items"].keys()
                                else fields[field_name]["items"][item.text]
                            )
                        else:
                            val = item.text
                        # If there are multiple values for a field append each new value for that
                        # field to a list, otherwise set the field value to whatever was determined
                        # above.
                        if "value" in fields[field_name].keys():
                            if not isinstance(fields[field_name]["value"], list):
                                fields[field_name]["value"] = [fields[field_name]["value"]]
                            fields[field_name]["value"].append(val)
                        else:
                            fields[field_name]["value"] = val
        return fields

    def process_xfa(self):
        """Extract all field information from an XFA file

        Returns
        -------

        result: dict
            A dictionary with the following structure:
                {
                    't_fields': List of all fields in template,
                    'cell_values': A key : value listing of all fields in the form, both with and without data
                }
        """

        # Get fields from template namespace
        t_fields = self.get_fields_from_template()

        # Get form values from dataset namespace
        d_fields = self.get_fields_from_dataset(t_fields)

        cell_values = {
            f"{field['section']}.{field['name']}": field["value"]
            for field in d_fields.values()
            if "value" in field.keys()
        }

        result = {
            't_fields': t_fields,
            "cell_values": cell_values,
        }
        return result
