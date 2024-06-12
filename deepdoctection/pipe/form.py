from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1
import xml.etree.ElementTree as ET
import re


class AcroFormHandler:
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
            "tot_columns": len(fields),
            "column_names": list(fields.keys()),
            't_fields': t_fields,
            "cell_values": {v['/T']: None if '/V' not in v.keys() else v['/V'] for v in fields.values()},
        }
        return result


class XFAHandler:
    def __init__(self, acroform):
        xfa = resolve1(acroform["XFA"])
        self.xml_root = self.get_xfa_xml(xfa)
        self.namespaces = self.get_namespaces()
        self.data = self.process_xfa()

    def get_xfa_xml(self, xfa):
        objs = [resolve1(x).get_data().decode() for n, x in enumerate(xfa) if n % 2 == 1]
        xstr = "".join(objs)
        root = ET.fromstring(xstr)
        return root

    def get_namespaces(self):
        namespaces = {}
        for elem in list(self.xml_root):
            ns, tag = re.match(r'\{(.+)\}(.+)', elem.tag).groups()
            namespaces[tag] = ns
        return namespaces

    def get_fields_from_template(self, elem=None, result={}, parent=None):
        """
        :param elem:
        :param namespaces:
        :param result:
        :param parent:

        Recursively parses a template namespace tree from an XFA document, extracting all necessary child elements
        (presently forms, subforms, and fields)

        As currently written, this function will not work on a generic (non-eSTAR) XFA document, as it relies on the
        field names to contain certain information. However, it seems that the data type of the field is contained as
        a subelement of the <ui> subelement. Here's the list of all the <ui> subelements:
        {'{http://www.xfa.org/schema/xfa-template/3.3/}button',
        '{http://www.xfa.org/schema/xfa-template/3.3/}checkButton',
        '{http://www.xfa.org/schema/xfa-template/3.3/}choiceList',
        '{http://www.xfa.org/schema/xfa-template/3.3/}dateTimeEdit',
        '{http://www.xfa.org/schema/xfa-template/3.3/}imageEdit',
        '{http://www.xfa.org/schema/xfa-template/3.3/}numericEdit',
        '{http://www.xfa.org/schema/xfa-template/3.3/}signature',
        '{http://www.xfa.org/schema/xfa-template/3.3/}textEdit'}

        And because it's not possible to rely on the word "attachment" being in the field name that won't work going
        forward. However, it looks like there's always a <button> tag. Here's the list of all of the subelements (all
        levels of the tree) of the eSTAR attachment fields:
        {'{http://www.xfa.org/schema/xfa-template/3.3/}assist',
        '{http://www.xfa.org/schema/xfa-template/3.3/}bind',
        '{http://www.xfa.org/schema/xfa-template/3.3/}border',
        '{http://www.xfa.org/schema/xfa-template/3.3/}button',
        '{http://www.xfa.org/schema/xfa-template/3.3/}caption',
        '{http://www.xfa.org/schema/xfa-template/3.3/}color',
        '{http://www.xfa.org/schema/xfa-template/3.3/}edge',
        '{http://www.xfa.org/schema/xfa-template/3.3/}event',
        '{http://www.xfa.org/schema/xfa-template/3.3/}fill',
        '{http://www.xfa.org/schema/xfa-template/3.3/}font',
        '{http://www.xfa.org/schema/xfa-template/3.3/}para',
        '{http://www.xfa.org/schema/xfa-template/3.3/}script',
        '{http://www.xfa.org/schema/xfa-template/3.3/}speak',
        '{http://www.xfa.org/schema/xfa-template/3.3/}text',
        '{http://www.xfa.org/schema/xfa-template/3.3/}ui',
        '{http://www.xfa.org/schema/xfa-template/3.3/}value'}

        The <script> tag is where I'm currently getting useful information about what section of the document an
        attachment is attached to. I'm not sure where that sits in the hierarchy under the <field> tag, but it's
        there somewhere.

        I also don't know if the AttachmentManifest is generalizable to all XFA documents, but a boy can dream, can't he...
        """
        result = {} if result is None else result
        elem = elem if elem is not None else self.xml_root.find(".//template:template", self.namespaces)

        tag_name = elem.tag.split("}")[-1]
        elem_name = tag_name if "name" not in elem.attrib.keys() else elem.attrib["name"]
        if (
                tag_name == "subform"
        ):  # if tag is a subform save its name as the parent of subsequent fields
            parent = (
                None
                if elem_name == "root"
                else elem_name
                if parent is None
                else f"{parent}.{elem_name}"
            )
        elif tag_name == "field":  # if the tag is a field tag...
            # ignore uninteresting element types
            if (not re.search("delete", elem_name.lower())
                    and not re.search("example", elem_name.lower())
                    and not re.search("tips", elem_name.lower())
            ):
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
                    name_tags = [
                        "caption",
                        "toolTip",
                    ]  # field info can come from one of two places
                    for tag in name_tags:
                        cur = elem.find(f".//template:{tag}", self.namespaces)
                        if cur is not None:
                            if not len(
                                    name
                            ):  # pull the field name and text from the element text...unless the field name was already found in the other tag type
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
        """
        :param fields:
        :param datasets:
        :param namespaces:

        Reads the field list generated by get_fields_from_template(), finds each of the fields in the dataset namespace, and extracts the vield value
        """
        datasets = self.xml_root.find(".//datasets:datasets", self.namespaces)

        for field_name, field in fields.items():
            elem = datasets.findall(f".//{field_name}")
            if elem is not None:
                for item in elem:
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
                        if "value" in fields[field_name].keys():
                            if not isinstance(fields[field_name]["value"], list):
                                fields[field_name]["value"] = [fields[field_name]["value"]]
                            fields[field_name]["value"].append(val)
                        else:
                            fields[field_name]["value"] = val
        return fields

    def process_xfa(self, ):
        """
        :param pdf

        Extract all field information from an XFA file
        """

        # Get fields from template namespace
        t_fields = self.get_fields_from_template(elem=None)

        # Get form values from dataset namespace
        d_fields = self.get_fields_from_dataset(t_fields)

        # Create list of field values and return dict result
        column_names = [
            field["name"] for field in d_fields.values() if "value" in field.keys()
        ]
        cell_values = {
            f"{field['section']}.{field['name']}": field["value"]
            for field in d_fields.values()
            if "value" in field.keys()
        }

        result = {
            # "form_id": doc_id,
            # "form_pages": pages,
            "tot_columns": len(column_names),
            "column_names": column_names,
            't_fields': t_fields,
            "cell_values": cell_values,
            # "bucket_name": bucket,
            # "object_key": doc_id,
        }
        return result


class FormHandler:
    """
    This is functional but a bit of a mess:

    1) There are bits of code scattered around that apply only to eSTAR docs
    2) The list of objects being output by process_acroform and process_xfa match, but it's unclear that they're what's needed
    3) The objects currently being put into the result object are
    """

    def __init__(self, pdf):
        pdf_bytes = pdf.stream.raw
        parser = PDFParser(pdf_bytes)
        doc = PDFDocument(parser)
        catalog = resolve1(doc.catalog)

        self.formtype = None
        self.data = None
        self.attachments = self.get_attachments(pdf)

        if 'AcroForm' in catalog.keys():
            acroform = resolve1(catalog['AcroForm'])
            if 'XFA' in acroform.keys():
                self.formtype = 'XFA'
                form = XFAHandler(acroform)
                self.data = form.data
                # self.get_attachments_from_manifest()
                self.label_attachments()

            elif 'Fields' in acroform.keys():
                self.formtype = 'AcroForm'
                form = AcroFormHandler(pdf)
                self.data = form.data

    def get_attachments(self, pdf):
        """
        Should apply to all PDFs
        """
        result = {}
        pdf_root = pdf.trailer['/Root']
        if '/Names' in pdf_root.keys() and '/EmbeddedFiles' in pdf_root['/Names'].keys():
            attachments = None if '/Names' not in pdf_root['/Names']['/EmbeddedFiles'].keys() else [x for n, x in
                                                                                                    enumerate(pdf_root[
                                                                                                                  '/Names'][
                                                                                                                  '/EmbeddedFiles'][
                                                                                                                  '/Names'])
                                                                                                    if n % 2 == 1]
            for item in attachments:
                filespec = item.get_object()
                fn = filespec['/F']
                pdf_bytes = filespec['/EF']['/F'].get_data()
                desc = fn if '/Desc' not in filespec.keys() else filespec['/Desc']
                # result[fn] = {'desc': desc, 'pdf_bytes': pdf_bytes}
                result[fn] = {'desc': desc}
        return result

    def label_attachments(self):
        """
        Applies only to eSTAR
        """
        for fn, info in self.attachments.items():
            cur = next((i for i in self.data['t_fields'].values() if i['name_tag'] == info['desc']), None)
            self.attachments[fn]['section'] = cur['section']

    def get_attachments_from_manifest(self):
        """
        Hopefully applies to all XFAs but may apply only to eSTAR
        """
        manifest = self.data['t_fields']['AttachmentManifest']['value']
        manifest_list = re.findall('<<(.+?)>>', manifest)
        for item in manifest_list:
            key, val = item.split('|')
            self.attachments[key]['path'] = val

    def clean_name(self, s, n=50):
        """
        :param object_file_metadata:
        :param deserialized_object:
        :param premarket_bucket:

        The files from the metadata must be checked first if they are XFA format.
        If yes= use Peter's estars script, if no, but it's estar, use estars textract script,
        if neither estars nor XFA, use general forms extraction script.\
        These should be filtered down to which files we think will contain forms:
            1. Cover Letters
            2. Summaries
        """
        result = s.lower()
        result = re.sub('[^a-z0-9]+', ' ', result)
        result = re.sub(r'\s+', '_', result.strip())
        return result[:n]

