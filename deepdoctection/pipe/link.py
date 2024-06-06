
from typing import List, Dict, Literal, Union, Mapping, Optional

from ..pipe.base import PipelineComponent
from ..datapoint.image import Image
from ..datapoint.annotation import ImageAnnotation
from ..pipe.registry import pipeline_component_registry
from ..utils.detection_types import JsonDict
from ..mapper.maputils import MappingContextManager
from ..utils.settings import Relationships

@pipeline_component_registry.register("MultiPageLinkingService")
class MultiPageLinkingService(PipelineComponent):
    """
    
    """
    def __init__(
        self,
        linking_func_list: List[
            Dict[Literal['category_names', 'func'], Mapping[
                Union[ImageAnnotation, Image], Union[ImageAnnotation, Image]]
            ]
        ]
    ):
        self._cached_datapoint: Optional[Image] = None
        self.linking_func_list = linking_func_list
   

    def serve(self, dp: Image) -> None:
        if self._cached.datapoint is not None:
            for func_dict in self.linking_func_list:
                inputs_1 = self._cached_datapoint.get_annotation(category_names=self.linking_func_list['category_names'])
                inputs_2 = self.dp.get_annotation(category_names=self.linking_func_list['category_names'])
                for input_1 in inputs_1:
                    for input_2 in inputs_2:
                        if func_dict['func'](input_1, input_2):
                            pass
                            
                            with MappingContextManager(dp_name=dp.file_name):
                                matched_percursor_anns = "" #np.take(child_anns, child_index)  # type: ignore
                                matched_sucessor_anns = "" #np.take(parent_anns, parent_index)  # type: ignore

                                for idx, parent in enumerate(matched_sucessor_anns):
                                    parent.dump_relationship(Relationships.child, matched_percursor_anns[idx].annotation_id)
                            
        self._cached.datapoint = dp # consistency check

    def clone(self) -> "PipelineComponent": # What should be cloned?
        return self.__class__(self._cached_datapoint, self.linking_func_list)

    def get_meta_annotation(self) -> JsonDict:
        return dict([("image_annotations", []), 
        ("sub_categories", {}), 
        ("relationships", {parent: {Relationships.child} for parent in self._cached_datapoint}), # This needs to be checked
        ("summaries", [])])