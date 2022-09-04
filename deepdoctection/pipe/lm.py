# -*- coding: utf-8 -*-
# File: tokenclass.py

# Copyright 2021 Dr. Janis Meyer. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Module for token classification pipeline
"""
from copy import copy
from typing import Any, Callable, List, Mapping, Optional, Tuple

from ..datapoint.image import Image
from ..extern.base import LMSequenceClassifier, LMTokenClassifier
from ..mapper.laylmstruct import LayoutLMFeatures
from ..utils.detection_types import JsonDict
from ..utils.settings import PageType, WordType, LayoutType
from .base import LanguageModelPipelineComponent
from .registry import pipeline_component_registry


@pipeline_component_registry.register("LMTokenClassifierService")
class LMTokenClassifierService(LanguageModelPipelineComponent):
    """
    Pipeline component for token classification

    **Example**

        .. code-block:: python

            # setting up compulsory ocr service
            tesseract_config_path = ModelCatalog.get_full_path_configs("/dd/conf_tesseract.yaml")
            tess = TesseractOcrDetector(tesseract_config_path)
            ocr_service = TextExtractionService(tess)

            # hf tokenizer and token classifier
            tokenizer = LayoutLMTokenizerFast.from_pretrained("microsoft/layoutlm-base-uncased")
            layoutlm = HFLayoutLmTokenClassifier(categories= ['B-ANSWER', 'B-HEAD', 'B-QUESTION', 'E-ANSWER',
                                                               'E-HEAD', 'E-QUESTION', 'I-ANSWER', 'I-HEAD',
                                                               'I-QUESTION', 'O', 'S-ANSWER', 'S-HEAD', 'S-QUESTION'])

            # token classification service
            layoutlm_service = LMTokenClassifierService(tokenizer,layoutlm,image_to_layoutlm)

            pipe = DoctectionPipe(pipeline_component_list=[ocr_service,layoutlm_service])

            path = "path/to/some/form"
            df = pipe.analyze(path=path)

            for dp in df:
                ...
    """

    def __init__(
        self,
        tokenizer: Any,
        language_model: LMTokenClassifier,
        mapping_to_lm_input_func: Callable[..., Callable[[Image], Optional[LayoutLMFeatures]]],
        default_token_classes: Optional[Mapping[str, Tuple[str, int]]] = None,
    ) -> None:
        """
        :param tokenizer: Token classifier, typing allows currently anything. This will be changed in the future
        :param language_model: language model token classifier
        :param mapping_to_lm_input_func: Function mapping image to layout language model features
        """
        self.language_model = language_model
        if default_token_classes is not None:
            assert WordType.token_class in default_token_classes
            assert WordType.tag in default_token_classes
            assert WordType.token_tag in default_token_classes
        self.default_token_class = default_token_classes
        super().__init__(tokenizer, mapping_to_lm_input_func)

    def serve(self, dp: Image) -> None:
        lm_input = self.mapping_to_lm_input_func(tokenizer=self.tokenizer)(dp)
        if lm_input is None:
            return
        lm_output = self.language_model.predict(**lm_input)

        # turn to word level predictions and remove all special tokens
        lm_output = [
            token
            for token in lm_output
            if token.token_id
            not in [self.tokenizer.cls_token_id, self.tokenizer.sep_token_id, self.tokenizer.pad_token_id]
            and not token.token.startswith("##")
        ]

        words_populated: List[str] = []
        for token in lm_output:
            if token.uuid not in words_populated:
                self.dp_manager.set_category_annotation(token.semantic_name, None, WordType.token_classn, token.uuid)
                self.dp_manager.set_category_annotation(token.bio_tag, None, WordType.tag, token.uuid)
                self.dp_manager.set_category_annotation(token.class_name, token.class_id, WordType.token_tag, token.uuid)
                words_populated.append(token.uuid)

        if self.default_token_class is not None:
            word_anns = dp.get_annotation(LayoutType.word)
            for word in word_anns:
                if WordType.semantic_name not in word.sub_categories:
                    self.dp_manager.set_category_annotation(
                        self.default_token_class[WordType.semantic_name][0], None, WordType.semantic_name, word.annotation_id
                    )
                if WordType.tag not in word.sub_categories:
                    self.dp_manager.set_category_annotation(
                        self.default_token_class[WordType.tag][0], None, WordType.tag, word.annotation_id
                    )
                if WordType.token_tag not in word.sub_categories:
                    self.dp_manager.set_category_annotation(
                        self.default_token_class[WordType.token_tag][0],
                        self.default_token_class[WordType.token_tag][1],
                        WordType.token_tag,
                        word.annotation_id,
                    )

    def clone(self) -> "LMTokenClassifierService":
        return self.__class__(
            copy(self.tokenizer),
            self.language_model.clone(),
            copy(self.mapping_to_lm_input_func),
            self.default_token_class,
        )

    def get_meta_annotation(self) -> JsonDict:
        return dict(
            [
                ("image_annotations", []),
                ("sub_categories", {LayoutType.word: {WordType.token_class, WordType.tag, WordType.token_tag}}),
                ("relationships", {}),
                ("summaries", []),
            ]
        )


@pipeline_component_registry.register("LMSequenceClassifierService")
class LMSequenceClassifierService(LanguageModelPipelineComponent):
    """
    Pipeline component for sequence classification

    **Example**

        .. code-block:: python

            # setting up compulsory ocr service
            tesseract_config_path = ModelCatalog.get_full_path_configs("/dd/conf_tesseract.yaml")
            tess = TesseractOcrDetector(tesseract_config_path)
            ocr_service = TextExtractionService(tess)

            # hf tokenizer and token classifier
            tokenizer = LayoutLMTokenizerFast.from_pretrained("microsoft/layoutlm-base-uncased")
            layoutlm = HFLayoutLmSequenceClassifier("path/to/config.json","path/to/model.bin",
                                                     categories=["HANDWRITTEN", "PRESENTATION", "RESUME"])

            # token classification service
            layoutlm_service = LMSequenceClassifierService(tokenizer,layoutlm, image_to_layoutlm_features)

            pipe = DoctectionPipe(pipeline_component_list=[ocr_service,layoutlm_service])

            path = "path/to/some/form"
            df = pipe.analyze(path=path)

            for dp in df:
                ...

    """

    def __init__(
        self,
        tokenizer: Any,
        language_model: LMSequenceClassifier,
        mapping_to_lm_input_func: Callable[..., Callable[[Image], Optional[LayoutLMFeatures]]],
    ) -> None:
        """
        :param tokenizer: Tokenizer, typing allows currently anything. This will be changed in the future
        :param language_model: language model sequence classifier
        :param mapping_to_lm_input_func: Function mapping image to layout language model features
        """
        self.language_model = language_model
        super().__init__(tokenizer, mapping_to_lm_input_func)

    def serve(self, dp: Image) -> None:
        lm_input = self.mapping_to_lm_input_func(tokenizer=self.tokenizer, return_tensors="pt")(dp)
        if lm_input is None:
            return
        lm_output = self.language_model.predict(**lm_input)
        self.dp_manager.set_summary_annotation(
            PageType.document_type, lm_output.class_name, lm_output.class_id, None, lm_output.score
        )

    def clone(self) -> "LMSequenceClassifierService":
        return self.__class__(copy(self.tokenizer), self.language_model.clone(), copy(self.mapping_to_lm_input_func))

    def get_meta_annotation(self) -> JsonDict:
        return dict(
            [
                ("image_annotations", []),
                ("sub_categories", {}),
                ("relationships", {}),
                ("summaries", [PageType.language]),
            ]
        )
