from typing import List, Dict, Literal, Union, Mapping, Optional

from ..pipe.base import PipelineComponent
from ..datapoint.image import Image
from ..pipe.registry import pipeline_component_registry
from ..utils.detection_types import JsonDict


@pipeline_component_registry.register("MultiPageLinkingService")
class MultiPageLinkingService(PipelineComponent):
    """

    """

    def __init__(
            self,
            linking_func_list: List[
                Dict[Literal['category_names', 'func'], Mapping[
                    Union[ImageAnnotation, Image], Union[ImageAnnotation, Image], bool]
                ]
            ]
    ):
        self._cached_datapoint: Optional[Image] = None
        self.linking_func_list = linking_func_list

    def serve(self, dp: Image) -> None:
        if self._cached.datapoint is not None:
            for func_dict in self.linking_func_list:
                inputs_1 = self._cached_datapoint.get_annotation(
                    category_names=self.linking_func_list['category_names'])
                inputs_2 = self.dp.get_annotation(category_names=self.linking_func_list['category_names'])
                for input_1 in inputs_1:
                    for input_2 in inputs_2:
                        if func_dict['func'](input_1, input_2):
                            pass

        self._cached.datapoint = dp  # consistency check

    def get_meta_annotation(self) -> JsonDict:
        pass

    def clone(self) -> PipelineComponent:
        pass