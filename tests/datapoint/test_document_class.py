""" Test module for Document class in the datapoint.view module """

import sys
import pytest

sys.path.insert(0, "/home/ec2-user/SageMaker/deepdoctection/")

from deepdoctection.datapoint.view import Document
from detect import get_document_pages

files_folder = "test_files_multipage"
paragraph_file_name = "test_file_paragraph.pdf"
table_file_name = "test_file_table.pdf"

pages_for_paragraph = get_document_pages(
    files_folder, paragraph_file_name
)  # Get page dataflow list from the multi-paged paragraph test file
pages_for_table = get_document_pages(
    files_folder, table_file_name
)  # Get page dataflow list from the multi-paged table test file

document = Document.from_pages(
    pages_for_paragraph
)  # Document class instance object to test the individual (protected) methods

document_for_paragraph = Document.from_pages(
    pages_for_paragraph
)  # Document class instance object to specifically test for multi-paged paragraph
document_for_table = Document.from_pages(
    pages_for_table
)  # Document class instance object to specifically test for multi-paged tables


def test_is_there_table():
    # test cases with table_len = 3, 0, -1
    assert document._is_there_table(3)
    assert not document._is_there_table(0)
    assert not document._is_there_table(-1)


def test_get_page_bounding_box():
    # To mock the data
    class PageEmbeddings:
        def __init__(self, ulx, uly, lrx, lry):
            self.ulx = ulx
            self.uly = uly
            self.lrx = lrx
            self.lry = lry

    page_embeddings_object_1 = PageEmbeddings(10, 20, 100, 200)
    page_embeddings_object_2 = PageEmbeddings(50, 60, 150, 250)

    page_embeddings = {
        "page1": page_embeddings_object_1,
        "page2": page_embeddings_object_2,
    }
    # Test case for page1
    page_id = "page1"
    expected_bbox = {"x1": 10, "y1": 20, "x2": 100, "y2": 200}
    assert document._get_page_bounding_box(page_embeddings, page_id) == expected_bbox

    # Test case for page2
    page_id = "page2"
    expected_bbox = {"x1": 50, "y1": 60, "x2": 150, "y2": 250}
    assert document._get_page_bounding_box(page_embeddings, page_id) == expected_bbox

    # Test case for non-existing page
    page_id = "page3"
    with pytest.raises(KeyError):
        document._get_page_bounding_box(page_embeddings, page_id)


def test_get_unique_id():

    # Test data
    bbox = {"x1": 50, "y1": 60, "x2": 150, "y2": 250}

    expected_unique_id = 510
    assert document._get_unique_id(bbox) == expected_unique_id


def test_format_bbox():
    # Mock - List of bbox coordinates
    bbox = [10, 230, 40, 350]
    expected_result = {"x1": 10, "x2": 40, "y1": 230, "y2": 350}
    unexpected_result = {"x1": 10, "x2": 250, "y1": 10, "y2": 350}
    assert document._format_bbox(bbox) == expected_result
    assert not document._format_bbox(bbox) == unexpected_result


def test_get_lowest_page_num():
    # Mock the doc_page_metadata_list
    doc_page_metadata_list = [
        {"page_num": 1},
        {"page_num": 3},
        {"page_num": 2},
    ]
    # Call the function
    lowest_page_num = document._get_lowest_page_num(doc_page_metadata_list)

    # Check if the result matches the expected value
    assert lowest_page_num == 1


def test_not_end_with_fullstop():
    # Test with a text that ends with a full stop
    text_with_fullstop = "This is a sentence."
    assert document._not_end_with_fullstop(text_with_fullstop) is False

    # Test with a text that does not end with a full stop
    text_without_fullstop = "This is another sentence"
    assert document._not_end_with_fullstop(text_without_fullstop) is True

    # Test with an empty string
    empty_string = ""
    assert document._not_end_with_fullstop(empty_string) is False

    # Test with a single character string
    single_character = "!"
    assert document._not_end_with_fullstop(single_character) is False


def test_is_paragraph_in_table():
    # Define test data
    table_bboxes = [
        {"x1": 100, "y1": 200, "x2": 300, "y2": 400},
    ]  # Sample table bounding box

    paragraph_bbox = {
        "x1": 120,
        "y1": 250,
        "x2": 180,
        "y2": 350,
    }  # Sample paragraph bounding box that falls in the table bbox
    paragraph_bbox_outside = {
        "x1": 400,
        "y1": 450,
        "x2": 500,
        "y2": 550,
    }  # Sample paragraph bounding box that falls outside the table bbox

    assert document._is_paragraph_in_table(paragraph_bbox, table_bboxes) == True
    assert (
        document._is_paragraph_in_table(paragraph_bbox_outside, table_bboxes) == False
    )


def test_get_page_table_data():
    # Define test data
    page_num = 21
    page_metadata_list = [
        {"page_num": 12, "page_name": "micron"},
        {"page_num": 21, "page_name": "bird"},
        {"page_num": 2, "page_name": "eucalps"},
    ]
    expected_metadata_two = {"page_num": 21, "page_name": "bird"}
    assert (
        document._get_page_table_data(page_metadata_list, page_num)
        == expected_metadata_two
    )
    page_num = 4
    assert document._get_page_table_data(page_metadata_list, page_num) is None


def test_delete_processed_data():
    # Define test data
    unique_id = 403.44000000000005
    page_metadata_list = [
        {
            "bbox": {"x1": 253.45, "y1": 129.24, "x2": 10.9, "y2": 228.15},
            "page_name": "micron",
        },
        {
            "bbox": {"x1": 243.15, "y1": 159.04, "x2": 9.19, "y2": 298.35},
            "page_name": "bird",
        },
        {
            "bbox": {"x1": 53.25, "y1": 119.04, "x2": 12.9, "y2": 218.25},
            "page_name": "eucalps",
        },
    ]
    expected_metadata = [
        {
            "bbox": {"x1": 253.45, "y1": 129.24, "x2": 10.9, "y2": 228.15},
            "page_name": "micron",
        },
        {
            "bbox": {"x1": 243.15, "y1": 159.04, "x2": 9.19, "y2": 298.35},
            "page_name": "bird",
        },
    ]
    assert (
        document._delete_processed_data(page_metadata_list, unique_id)
        == expected_metadata
    )


def test_is_close_to_footer():
    # Define test data
    page_height = 100  # Example page height
    upper_y_coord = 80  # Example upper Y coordinate
    footer_height = 0.8 * page_height  # Calculate expected footer height

    # Call the function under test
    result = document._is_close_to_footer(page_height, upper_y_coord)

    # Perform assertion to check if the result matches the expected outcome
    assert result == (upper_y_coord > footer_height)

    # Additional test with lower Y coordinate to ensure negative case
    lower_y_coord = 20  # Example lower Y coordinate
    result_lower = document._is_close_to_footer(page_height, lower_y_coord)
    assert result_lower == (lower_y_coord > footer_height)


def test_is_close_to_header():
    # Define test data
    page_height = 100  # Example page height
    lower_y_coord = 20  # Example lower Y coordinate
    header_height = 0.5 * page_height  # Calculate expected header height

    # Call the function under test
    result = document._is_close_to_header(page_height, lower_y_coord)

    # Perform assertion to check if the result matches the expected outcome
    assert result == (lower_y_coord < header_height)


def test_detect_multi_page_entities():

    multi_page_text = document_for_paragraph.detect_multi_page_entities()

    assert "text" in multi_page_text
    assert multi_page_text["text"] is not None
    assert (
        multi_page_text["text"]["0"][0]["text"]
        == "Whether you're registered for in-person attendance at the June 4 Wellness Symposium or not, you can join us for a welcome message from CDRH Center Director Jeff Shuren and Senior Leadership, followed by a keynote address from Jeff Vargas, president, and CEO of Generationology LLC, onintergenerational connections"
    )
    assert (
        multi_page_text["text"]["0"][1]["text"]
        == "in the workplace. Learn how to enhance, expand, and leverage individual skills to unleash the full potential of teams."
    )

    """
    # This would be completed when the model detects table on the test file accurately

    multi_page_table = document_for_table.detect_multi_page_entities()
    assert "table" in multi_page_table
    assert multi_page_text["table"] is not None
    """
