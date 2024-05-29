from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1
import xml.etree.ElementTree as ET
import re
import json


class FormHandler:
    def __init__(self, pdf):
        pdf_bytes = pdf.stream.raw
        parser = PDFParser(pdf_bytes)
        doc = PDFDocument(parser)
        catalog = resolve1(doc.catalog)

        if 'AcroForm' not in catalog.keys():
            self.result = None
        else:
            acroform = resolve1(catalog['AcroForm'])
            if 'XFA' in acroform.keys():
                xfa = resolve1(acroform["XFA"])
                self.result = self.process_xfa_estars(xfa)

            elif 'Fields' in acroform.keys():
                self.result = self.process_acroform(pdf)

    def process_acroform(self, pdf):
        fields = pdf.get_fields()
        t_fields = {}
        for key, val in fields.items():
            t_fields[key] = {
                "section": None,
                "field_name": key,
                "name": val['/T'],
                "name_tag": None if '/V' not in val.keys() else val['/V'],
            }

        result = {
            "tot_columns": len(fields),
            "column_names": list(fields.keys()),
            't_fields': t_fields,
            "cell_values": None,
        }
        return result

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
        result = re.sub("[^a-z0-9]+", " ", result)
        result = re.sub("\s+", "_", result.strip())
        return result[:n]

    def get_fields_from_template(self, elem, namespaces, result={}, parent=None):
        """
        :param elem:
        :param namespaces:
        :param result:
        :param parent:

        Recursively parses a template namespace tree from an XFA document, extracting all necessary child elements
        (presently forms, subforms, and fields)
        """

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
            if (
                not re.search("add", elem_name.lower())
                and not re.search("delete", elem_name.lower())
                and not re.search("attachment", elem_name.lower())
                and not re.search("example", elem_name.lower())
                and not re.search("tips", elem_name.lower())
            ):
                name = ""
                name_tags = [
                    "caption",
                    "toolTip",
                ]  # field info can come from one of two places
                for tag in name_tags:
                    cur = elem.find(f".//template:{tag}", namespaces)
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
                    items = elem.findall(".//template:items", namespaces)
                    if len(items) == 2:
                        result[elem_name]["items"] = dict(
                            zip(list(items[1].itertext()), list(items[0].itertext()))
                        )

        # see if there are subelements and recurse into them if necessary
        subs = elem.findall("*", namespaces)
        if len(subs):
            for item in subs:
                result = self.get_fields_from_template(item, namespaces, result, parent)
        return result

    def get_fields_from_dataset(self, fields, datasets, namespaces):
        """
        :param fields:
        :param datasets:
        :param namespaces:

        Reads the field list generated by get_fields_from_template(), finds each of the fields in the dataset namespace, and extracts the vield value
        """
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

    def process_xfa_estars(self, xfa):
        """
        :param pdf

        Extract all field information from an XFA file
        """
        objs = [resolve1(x).get_data().decode() for n, x in enumerate(xfa) if n % 2 == 1]
        xstr = "".join(objs)

        # Parse XFA XML
        root = ET.fromstring(xstr)
        namespaces = {}
        for elem in list(root):
            ns, tag = re.match("\{(.+)\}(.+)", elem.tag).groups()
            namespaces[tag] = ns

        # Get fields from template namespace
        template = root.find(".//template:template", namespaces)
        t_fields = self.get_fields_from_template(template, namespaces)

        # Get form values from dataset namespace
        datasets = root.find(".//datasets:datasets", namespaces)
        d_fields = self.get_fields_from_dataset(t_fields, datasets, namespaces)

        # Create list of field values and return dict result
        column_names = [
            field["field_name"] for field in d_fields.values() if "value" in field.keys()
        ]
        cell_values = {
            field["field_name"]: field["value"]
            for field in d_fields.values()
            if "value" in field.keys()
        }

        result = {
            #"form_id": doc_id,
            #"form_pages": pages,
            "tot_columns": len(column_names),
            "column_names": column_names,
            't_fields' : t_fields,
            "cell_values": json.dumps(cell_values),
            #"bucket_name": bucket,
            #"object_key": doc_id,
        }
        return result
