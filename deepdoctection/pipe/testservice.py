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

        df: DataFlow

        a = 1
        #self.streamer = PDFStreamer()
        #df = MapData(
        #    df,
        #    lambda dp: {"pdf_bytes": dp[0]},
        #)

    def clone(self):
        return self.__class__()

    def get_meta_annotation(self):
        #super().get_meta_annotation()
        return {'image_annotations': [], 'sub_categories': {}, 'relationships': {}, 'summaries': []}

    def serve(self, dp) -> None:
        print('SERVE!!!')
        super().serve()

    def get_pdf_stream(self, df):
        """
        Descends through a dataflow to find the bottommost element and extracts a PDF stream from it
        """

        result = None
        while 'df' in df.__dict__.keys():
            df = df.df
        for attr in df.__dict__.keys():
            obj = getattr(df, attr)
            if isinstance(obj, PDFStreamer):
                result = obj
        return result
