from abc import ABC

from .base import PipelineComponent
from .registry import pipeline_component_registry
from ..datapoint.image import Image

from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdftypes import resolve1
import xml.etree.ElementTree as ET
import re


class Resources:
    def __init__(self):
        pass

    def read_acroform_fields(self, acroform):
        # reads fields and data from a plain old AcroForm
        result = {}
        for fld in resolve1(acroform['Fields']):
            item = resolve1(fld)
            fieldname = item['T'].decode("utf-8")
            data = None if 'V' not in item.keys() else item['V'].decode("utf-8")
            result[fieldname] = data
        return result


@pipeline_component_registry.register("AcroFormParsingService")
class AcroFormParsingService():
    def __init__(self, pdf):
        print('AcroFormParsingService')
        #super().__init__("text_refinement")
        #self.resources = resources
        parser = PDFParser(pdf)
        doc = PDFDocument(parser)
        acroform = resolve1(doc.catalog["AcroForm"])
        if 'XFA' in acroform.keys():
            xfa = ProcessXFA(acroform)
            self.fields = xfa.cell_values
        elif 'Fields' in acroform.keys():
            self.fields = {}
            for fld in resolve1(acroform['Fields']):
                item = resolve1(fld)
                fieldname = item['T'].decode("utf-8")
                data = None if 'V' not in item.keys() else item['V'].decode("utf-8")
                self.fields[fieldname] = data
        else:
            self.fields = None
        print(self.fields)

    def serve(self, dp: Image) -> None:
        """
        Refines the text extraction results for the given document page (Image).

        :param dp: The document page as an Image object containing text extraction results.
        """
        # TODO: Implement the logic for refining text extraction results using the provided resources.
        pass

    def clone(self) -> "PipelineComponent":
        """
        Creates a copy of this TextRefinementService instance.
        """
        return self.__class__(self.resources)


class ProcessXFA:

    def __init__(self, acroform):
        xfa = acroform["XFA"]
        objs = [resolve1(x).get_data().decode() for n, x in enumerate(xfa) if n % 2 == 1]
        xstr = "".join(objs)
        self.xml = ET.fromstring(xstr)
        self.namespaces = self.get_namespaces()

        # Get fields from template namespace
        self.template_fields = self.get_fields_from_template()

        # Get form values from dataset namespace
        self.dataset_fields = self.get_fields_from_dataset()

        # Create list of field values and return dict result
        self.column_names = [
            field["field_name"] for field in self.dataset_fields.values() if "value" in field.keys()
        ]
        self.cell_values = {
            field["field_name"]: field["value"] for field in self.dataset_fields.values() if "value" in field.keys()
        }

    def get_namespaces(self):
        result = {}
        for elem in list(self.xml):
            ns, tag = re.match("\{(.+)\}(.+)", elem.tag).groups()
            result[tag] = ns
        return result

    def get_fields_from_template(self, elem=None, result={}, parent=None):
        """
        :param elem:
        :param result:
        :param parent:

        Recursively parses a template namespace tree from an XFA document, extracting all necessary child elements
        (presently forms, subforms, and fields)
        """
        # start at the XML root if this is the first time the function has been called
        elem = elem if elem is not None else self.xml.find(".//template:template", self.namespaces)

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
                    cur = elem.find(f".//template:{tag}", self.namespaces)
                    if cur is not None:
                        if not len(
                                name
                        ):  # pull the field name and text from the element text...unless the field name was already
                            # found in the other tag type
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

    def get_fields_from_dataset(self):
        """
        Reads the field list generated by get_fields_from_template(), finds each of the fields in the dataset
        namespace, and extracts the vield value
        """
        fields = self.template_fields
        datasets = self.xml.find(".//datasets:datasets", self.namespaces)

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
