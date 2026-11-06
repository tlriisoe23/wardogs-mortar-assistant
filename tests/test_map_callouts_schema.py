import json
import os
import math

def test_map_callouts_json_schema():
    callouts_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'map_callouts.json')
    assert os.path.exists(callouts_file), "data/map_callouts.json must exist"

    with open(callouts_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert isinstance(data, dict), "Root should be a dictionary"

    for map_name, map_data in data.items():
        assert isinstance(map_name, str)
        assert isinstance(map_data, dict), f"Map data for {map_name} must be a dictionary"

        assert "locations" in map_data, f"Missing 'locations' in {map_name}"
        assert isinstance(map_data["locations"], list)

        for loc in map_data["locations"]:
            assert isinstance(loc, dict)
            assert "name" in loc and isinstance(loc["name"], str)

            assert "x" in loc and isinstance(loc["x"], (int, float)) and not isinstance(loc["x"], bool)
            assert math.isfinite(loc["x"]), "x must be finite"
            assert "y" in loc and isinstance(loc["y"], (int, float)) and not isinstance(loc["y"], bool)
            assert math.isfinite(loc["y"]), "y must be finite"

            if "normX" in loc:
                assert isinstance(loc["normX"], (int, float)) and not isinstance(loc["normX"], bool)
                assert math.isfinite(loc["normX"]), "normX must be finite"
            if "normY" in loc:
                assert isinstance(loc["normY"], (int, float)) and not isinstance(loc["normY"], bool)
                assert math.isfinite(loc["normY"]), "normY must be finite"

        assert "tactical" in map_data, f"Missing 'tactical' in {map_name}"
        assert isinstance(map_data["tactical"], list)
        for tac in map_data["tactical"]:
            assert isinstance(tac, dict)
            assert "name" in tac and isinstance(tac["name"], str)
            assert "kind" in tac and isinstance(tac["kind"], str)
            assert "color" in tac and isinstance(tac["color"], str)

            assert "x" in tac and isinstance(tac["x"], (int, float)) and not isinstance(tac["x"], bool)
            assert math.isfinite(tac["x"]), "x must be finite"
            assert "y" in tac and isinstance(tac["y"], (int, float)) and not isinstance(tac["y"], bool)
            assert math.isfinite(tac["y"]), "y must be finite"

        assert "zonesCount" in map_data, f"Missing 'zonesCount' in {map_name}"
        assert isinstance(map_data["zonesCount"], int) and not isinstance(map_data["zonesCount"], bool)
