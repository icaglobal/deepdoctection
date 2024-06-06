""" Multipage detection module """

import os

from deepdoctection.analyzer import dd
from deepdoctection.datapoint.view import Document


def get_document_pages(files_folder, file_name):
    """
    Gets the iterable datapoint flow representing the document pages after being analyzed by the deepdoctection pipeline.
    params
    ------
    files_folder: name of the folder placed in the root folder, where the test files are located
    file_name: The test file name
    returns
    ------
    Iterable list with items representing page dataflow from the deepdoctection analysis pipeline
    """

    config_overwrite = [
        "PT.LAYOUT.WEIGHTS=microsoft/table-transformer-detection/pytorch_model.bin",
        "PT.ITEM.WEIGHTS=microsoft/table-transformer-structure-recognition/pytorch_model.bin",
        "PT.ITEM.FILTER=['table']",
        "OCR.USE_DOCTR=True",
        "OCR.USE_TESSERACT=False",
    ]

    # Initialize the dd's analyzer pipeline
    analyzer = dd.get_dd_analyzer(config_overwrite=config_overwrite)
    current_dir: str = os.getcwd()

    file_path = os.path.join(current_dir, files_folder, file_name)

    df = analyzer.analyze(path=file_path)

    df.reset_state()  # Part of Deepdoctection API

    pages = []
    for page in list(iter(df)):
        pages.append(page)

    return pages


if __name__ == "__main__":

    files_folder = "test_files_multipage"  # Test folder name
    file_name = "test_file_paragraph.pdf"  # Change this to a file name in a directory located in the root directory and named "test_files"

    pages = get_document_pages(files_folder, file_name)

    # Instantiate the Document with collected pages
    document = Document.from_pages(pages)

    # Attempt to detect multipage entities
    multipage_entities = document.detect_multi_page_entities()

    # You might want to do something with `multipage_entities` returned here
    print("======= Multipage entities =======")
    print(multipage_entities)
