import deepdoctection as dd
from deepdoctection.pipe.form import FormHandler
from pypdf import PdfReader
import re

path = '../pdf/normal.pdf'
path = '../pdf/estar_nivd.pdf'
#path = '../pdf/acroform.pdf'

#analyzer = dd.get_dd_analyzer()
#df = analyzer.analyze(path=path)
#df.reset_state()
#pdf = analyzer.pdf_reader

pdf = PdfReader(open(path, 'rb'))
fh = FormHandler(pdf)
for fn, info in fh.attachments.items():
    print(fn)
    print(info)
    print()