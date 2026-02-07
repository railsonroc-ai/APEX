import pytest
from unittest.mock import patch, MagicMock
from main import fetch_item_data
from utils import load_config, save_data
import os
import json

@patch('requests.get')
def test_fetch_item_data_success(mock_get):
    mock_response = MagicMock()
    mock_response.json.return_value = {'id': 1, 'name': 'Test', 'value': 10.0}
    mock_response.raise_for_status.return_value = None
    mock_get.return_value = mock_response
    os.environ['API_KEY'] = 'test_key'
    result = fetch_item_data(1)
    assert result == {'id': 1, 'name': 'Test', 'value': 10.0}

def test_save_load_data(tmp_path):
    data = [{'id': 1, 'name': 'Item 1'}]
    output_file = str(tmp_path / "test_output.json")
    save_data(data, output_file)
    assert os.path.exists(output_file)
    with open(output_file) as f:
        loaded = json.load(f)
    assert loaded == data
