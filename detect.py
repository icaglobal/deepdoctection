import os
from deepdoctection.analyzer import dd
from deepdoctection.datapoint.view import Document

def get_pages_for_testing():

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
    files_folder = "test_files"
    file_name = "PMC497044.pdf" # Change this to a file name in a directory located in the root directory and named "test_files"

    file_path = os.path.join(current_dir, files_folder, file_name)

    df = analyzer.analyze(path=file_path)

    df.reset_state()  # Part of Deepdoctection API

    pages = []
    for page in list(iter(df)):
        pages.append(page)

    return pages

# Comment everything below out when not running detect.py script from the root directory
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
files_folder = "test_files"
file_name = "PMC497044.pdf" # Change this to a file name in a directory located in the root directory and named "test_files"

file_path = os.path.join(current_dir, files_folder, file_name)

df = analyzer.analyze(path=file_path)

df.reset_state()  # Part of Deepdoctection API

pages = []
for page in list(iter(df)):
    pages.append(page)
# Instantiate the Document with collected pages
document = Document.from_pages(pages)

# Attempt to detect multipage entities
multipage_entities = document.detect_multi_page_entities()

# You might want to do something with `multipage_entities` here
print("======= Multipage entities =======")
print(multipage_entities)