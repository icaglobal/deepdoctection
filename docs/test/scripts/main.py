import deepdoctection as dd
from deepdoctection.pipe.form import GetDoclevelObjects
from pypdf import PdfReader
import re

path = '../pdf/normal.pdf'
path = '../pdf/estar_nivd.pdf'
path = '../pdf/acroform.pdf'

#analyzer = dd.get_dd_analyzer()
#df = analyzer.analyze(path=path)
#df.reset_state()
#pdf = analyzer.pdf_reader

pdf = PdfReader(open(path, 'rb'))
dlo = GetDoclevelObjects(pdf)
form_fields = dlo.form.fields
for key, val in form_fields.items():
    print(val.field_name, val.value)
