import os
from deepdoctection.analyzer import dd

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
file_name = "PMC509421.pdf" # Change this to a single page file for testing

file_path = os.path.join(current_dir, files_folder, file_name)

df = analyzer.analyze(path=file_path)

df.reset_state()  # Part of Deepdoctection API

for page in list(iter(df)):
    print(page)

