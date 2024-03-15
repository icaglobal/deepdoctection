from .base import Pipeline, PipelineComponent, PredictorPipelineComponent
from ..utils.pdf_utils import PDFStreamer
from ..utils.detection_types import Pathlike
from .base import DataFlow
from .common import MapData
from ..dataflow.custom import CustomDataFromIterable

class TestService(PipelineComponent):
    def __init__(self):
        import os
        print('TestService')
        super().__init__(self)
        max_datapoints = 1000

        #file_name = os.path.split(path)[1]
        #prefix, suffix = os.path.splitext(file_name)
        df: DataFlow
        a = 1
        #self.streamer = PDFStreamer()
        #df = MapData(
        #    df,
        #    lambda dp: {"pdf_bytes": dp[0]},
        #)

    def clone(self):
        #super().clone()
        pass
    def get_meta_annotation(self):
        #super().get_meta_annotation()
        return {'image_annotations': [], 'sub_categories': {}, 'relationships': {}, 'summaries': []}
    def serve(self, dp):
        #super().serve()
        pass
