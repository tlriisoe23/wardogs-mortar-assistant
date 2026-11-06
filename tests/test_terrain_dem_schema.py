import json
import os
import math

def test_terrain_dem_json_schema():
    dem_file = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'data', 'terrain', 'terrain_dem.json')
    assert os.path.exists(dem_file), "terrain_dem.json must exist"

    with open(dem_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    assert isinstance(data, dict), "Root should be a dictionary"

    for map_name, map_data in data.items():
        assert isinstance(map_name, str)
        assert isinstance(map_data, dict)

        for key in ["minX", "maxX", "minY", "maxY", "reliefMeters"]:
            assert key in map_data, f"Missing {key}"
            val = map_data[key]
            assert isinstance(val, (int, float)) and not isinstance(val, bool)
            assert math.isfinite(val)

        assert "gridSize" in map_data
        assert isinstance(map_data["gridSize"], int) and not isinstance(map_data["gridSize"], bool)

        assert "heights" in map_data
        assert isinstance(map_data["heights"], list)
        for row in map_data["heights"]:
            assert isinstance(row, list)
            for h in row:
                assert isinstance(h, (int, float)) and not isinstance(h, bool)
                assert math.isfinite(h)

        assert "contours" in map_data
        assert isinstance(map_data["contours"], list)
        for contour in map_data["contours"]:
            assert isinstance(contour, dict)
            assert "z" in contour
            z = contour["z"]
            assert isinstance(z, (int, float)) and not isinstance(z, bool)

            assert "major" in contour
            assert isinstance(contour["major"], bool)

            assert "lines" in contour
            assert isinstance(contour["lines"], list)
            for line in contour["lines"]:
                assert isinstance(line, list)
                for pt in line:
                    assert isinstance(pt, (int, float)) and not isinstance(pt, bool)
                    assert math.isfinite(pt)
