import deepdoctection as dd
from deepdoctection.pipe.form import FormHandler
from pypdf import PdfReader

path = '../pdf/normal.pdf'
path = '../pdf/estar.pdf'
path = '../pdf/acroform.pdf'

#analyzer = dd.get_dd_analyzer()
#df = analyzer.analyze(path=path)
#df.reset_state()
#pdf = analyzer.pdf_reader

pdf = PdfReader(open(path, 'rb'))

af = FormHandler(pdf)
print(af.result)