import json
import os

def test_map_callouts_json_schema():
    callouts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'map_callouts.json')
    assert os.path.exists(callouts_file), "data/map_callouts.json must exist"

    with open(callouts_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert isinstance(data, dict), "Root should be a dictionary"

    for map_name, map_data in data.items():
        assert isinstance(map_name, str), "Map name should be a string"
        assert isinstance(map_data, dict), f"Data for map '{map_name}' should be a dictionary"

        assert "locations" in map_data, f"Map '{map_name}' must have a 'locations' array"
        assert isinstance(map_data["locations"], list), f"'locations' in map '{map_name}' should be a list"

        for idx, item in enumerate(map_data["locations"]):
            assert isinstance(item, dict), f"Item at index {idx} in map '{map_name}' should be a dictionary"

            # Required keys and their types
            assert "name" in item and isinstance(item["name"], str), f"Missing or invalid 'name' in map '{map_name}' at index {idx}"
            assert "x" in item and isinstance(item["x"], (int, float)), f"Missing or invalid 'x' in map '{map_name}' at index {idx}"
            assert "y" in item and isinstance(item["y"], (int, float)), f"Missing or invalid 'y' in map '{map_name}' at index {idx}"
            assert "normX" in item and isinstance(item["normX"], (int, float)), f"Missing or invalid 'normX' in map '{map_name}' at index {idx}"
            assert "normY" in item and isinstance(item["normY"], (int, float)), f"Missing or invalid 'normY' in map '{map_name}' at index {idx}"
