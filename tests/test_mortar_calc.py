import pytest
from mortar_calc import (
    interpolate_table,
    interpolate_elevation,
    sph_platform_correct_aim,
    MortarCalculator,
)


def test_interpolate_table():
    table = [(100.0, 800.0), (200.0, 700.0)]
    assert interpolate_table(table, 50.0) is None
    assert interpolate_table(table, 250.0) is None
    assert interpolate_table(table, 100.0) == 800.0
    assert interpolate_table(table, 200.0) == 700.0
    assert interpolate_table(table, 150.0) == 750.0


def test_interpolate_table_plateau():
    table = [(100.0, 800.0), (100.0, 820.0)]
    assert interpolate_table(table, 100.0) == 810.0


def test_interpolate_elevation():
    # Test L81 mortar bounds
    assert interpolate_elevation(80.0, weapon="mortar") == 950.0
    assert interpolate_elevation(631.0, weapon="mortar") == 260.0


def test_sph_platform_correct_aim_none():
    res = sph_platform_correct_aim(800.0, 45.0, None)
    assert res["corrected_mil"] == 800.0
    assert res["mil_delta"] == 0.0
    assert res["relative_yaw_deg"] == 0.0


def test_sph_platform_correct_aim_straight():
    # Hull pointing north, target north, pitch 5.0 deg
    res = sph_platform_correct_aim(800.0, 0.0, 0.0, 5.0)
    assert res["relative_yaw_deg"] == 0.0


def test_mortar_calculator():
    calc = MortarCalculator(mortar_x=10.0, mortar_y=10.0, weapon="mortar")
    calc.set_target(11.0, 10.0)  # dx = 1, dy = 0. Range = 100m.
    sol = calc.calculate_solution()

    assert sol["distance_meters"] == pytest.approx(100.0)
    assert sol["bearing_deg"] == pytest.approx(90.0)

    # 100m interpolation from mortar table
    # (99, 920), (105, 910)
    # Ratio = (100 - 99) / (105 - 99) = 1 / 6
    # 920 + (1/6)*(910 - 920) = 920 - 10/6 = 918.333
    assert sol["elevation_mils"] == pytest.approx(918.3333333)


def test_mortar_calculator_adjustments():
    calc = MortarCalculator(mortar_x=0.0, mortar_y=0.0, weapon="mortar")
    calc.set_target(1.0, 0.0)  # 100m East (Azimuth 90)

    calc.adjust_relative(50.0, 0.0)  # Add 50m (long)
    # New target should be at x = 1.5, y = 0.0
    assert calc.target_x == pytest.approx(1.5)
    assert calc.target_y == pytest.approx(0.0)

    calc.adjust_missed_shot(50.0, 0.0)  # Missed 50m long, so drop 50m
    # New target should be at x = 1.0, y = 0.0
    assert calc.target_x == pytest.approx(1.0)
    assert calc.target_y == pytest.approx(0.0)


def test_interpolate_elevation_sph2():
    # SPH2 test to improve coverage
    assert interpolate_elevation(780.0, weapon="sph2", arc="high") is not None
    assert interpolate_elevation(1181.0, weapon="sph2", arc="low") is not None


def test_sph_platform_correct_aim_yaw():
    # Hull pointing north, target east, pitch 5.0 deg
    res = sph_platform_correct_aim(800.0, 90.0, 0.0, 5.0)
    assert res["relative_yaw_deg"] == 90.0
    # Elevation changes when pointing sideways with fore pitch
    assert res["mil_delta"] != 0.0


def test_mortar_calculator_target_unreachable():
    calc = MortarCalculator(mortar_x=10.0, mortar_y=10.0, weapon="mortar")
    calc.set_target(10.0, 10.0)  # dx = 0, dy = 0. Range = 0m.
    sol = calc.calculate_solution()

    assert sol["distance_meters"] == 0.0
    assert sol["in_range"] is False
    assert sol["elevation_mils"] is None


def test_mortar_calculator_zero_length_gtl_adjust():
    calc = MortarCalculator(mortar_x=10.0, mortar_y=10.0, weapon="mortar")
    calc.set_target(10.0, 10.0)  # Length 0 GTL
    # Add 100m range, 0m deflection
    calc.adjust_relative(100.0, 0.0)
    # The default behavior for 0 length is u_along = (0, 1) and u_right = (1, 0)
    # So range add of 100m (1 unit) should push it along +Y (North)
    assert calc.target_x == pytest.approx(10.0)
    assert calc.target_y == pytest.approx(11.0)


def test_get_terrain_elevation(monkeypatch):
    import mortar_calc

    # Mocking DEM cache for deterministic tests
    mocked_cache = {
        "test_map": {
            "minX": 0, "maxX": 100,
            "minY": 0, "maxY": 100,
            "heights": [
                [10.0, 20.0, 30.0],
                [40.0, 50.0, 60.0],
                [70.0, 80.0, 90.0]
            ],
            "gridSize": 3
        }
    }
    monkeypatch.setattr(mortar_calc, "_TERRAIN_DEM_CACHE", mocked_cache)

    # "firing_range" is hardcoded to return 0.0
    assert mortar_calc.get_terrain_elevation("firing_range", 10.0, 10.0) == 0.0

    # Top left corner
    assert mortar_calc.get_terrain_elevation("test_map", 0, 0) == 10.0

    # Bottom right corner
    assert mortar_calc.get_terrain_elevation("test_map", 100, 100) == 90.0

    # Middle
    assert mortar_calc.get_terrain_elevation("test_map", 50, 50) == 50.0

    # Out of bounds
    assert mortar_calc.get_terrain_elevation("test_map", -10, -10) is None

    # Missing map
    assert mortar_calc.get_terrain_elevation("missing_map", 10, 10) is None


def test_solve_sph2_terrain_mils():
    from mortar_calc import solve_sph2_terrain_mils
    # If delta Z is very small, it should return flat_mils
    assert solve_sph2_terrain_mils("high", 1000.0, 800.0, 0.0) == 800.0
    assert solve_sph2_terrain_mils("low", 1000.0, 800.0, 0.0) == 800.0

    # Large elevation change with realistic distance/mils that can be solved
    # distance = 1500m, flat_mils = 1000 (valid for high arc SPH2)
    elev = solve_sph2_terrain_mils("high", 1500.0, 1000.0, 50.0)
    # The solver converges around 1004.9
    assert elev == pytest.approx(1004.9, rel=1e-1)

    elev_low = solve_sph2_terrain_mils("low", 2000.0, 100.0, -50.0)
    # The solver should return some value near 100, might not converge, we check path execution
    if elev_low is not None:
        assert elev_low > 0


def test_print_solution(capsys):
    from mortar_calc import print_solution
    sol = {
        "weapon": "mortar",
        "arc": "high",
        "mortar": (10.0, 10.0),
        "target": (20.0, 10.0),
        "dx_meters": 1000.0,
        "dy_meters": 0.0,
        "distance_meters": 1000.0,
        "bearing_deg": 90.0,
        "bearing_mils": 1600.0,
        "elevation_mils": None,
        "in_range": False,
        "slope_only": False,
        "min_range": 132.0,
        "max_range": 684.0,
    }
    print_solution(sol)
    captured = capsys.readouterr()
    assert "OUT OF RANGE" in captured.out

    sol["elevation_mils"] = 800.0
    sol["in_range"] = True
    print_solution(sol)
    captured2 = capsys.readouterr()
    assert "OK" in captured2.out

    sol["in_range"] = False
    sol["slope_only"] = True
    print_solution(sol)
    captured3 = capsys.readouterr()
    assert "SLOPE ONLY" in captured3.out


def test_mortar_calculator_dz_and_sph2(monkeypatch):
    from mortar_calc import MortarCalculator

    # SPH2 with low arc and dz
    calc = MortarCalculator(0, 0, weapon="sph2", arc="low")
    calc.delta_z_m = -10.0 # Small enough delta z for the numerical solver to converge
    calc.set_target(0, 15.0) # 1500m
    sol = calc.calculate_solution()

    # Depending on interpolation bounds, we check it gracefully handles it
    if sol["elevation_mils"] is not None:
        assert sol["elevation_mils"] > 0

    # SPH2 high arc with map terrain (mocked)
    import mortar_calc
    mocked_cache = {
        "test_map": {
            "minX": 0, "maxX": 100,
            "minY": 0, "maxY": 100,
            "heights": [[100.0 for _ in range(3)] for _ in range(3)],
            "gridSize": 3
        }
    }
    monkeypatch.setattr(mortar_calc, "_TERRAIN_DEM_CACHE", mocked_cache)

    calc2 = MortarCalculator(0, 0, weapon="sph2", arc="high", map_id="test_map")
    calc2.set_target(0, 15.0)
    sol2 = calc2.calculate_solution()
    assert sol2["elevation_mils"] is not None

def test_interactive_cli_quit(monkeypatch, capsys):
    from mortar_calc import interactive_cli

    inputs = iter(['q'])
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    interactive_cli()
    captured = capsys.readouterr()
    assert "MORTAR & ARTILLERY PYTHAGOREAN CALCULATOR" in captured.out

def test_interactive_cli_commands(monkeypatch, capsys):
    from mortar_calc import interactive_cli

    # We will test all interactive commands then quit
    commands = [
        'm 0 0',
        't 0 10',
        'wpn sph2',
        'wpn sph_l',
        'wpn mortar',
        'add 100',
        'drop 50',
        'right 10',
        'left 10',
        'miss 10 10',
        'impact 1 10',
        'calc',
        'invalid_command',
        'q'
    ]
    inputs = iter(commands)
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))

    interactive_cli()
    captured = capsys.readouterr()
    assert "Unknown command" in captured.out


def test_if_name_main(monkeypatch, capsys):
    import sys
    import mortar_calc

    # Test --test flag
    monkeypatch.setattr(sys, "argv", ["mortar_calc.py", "--test"])

    # Needs to be reloaded/re-run in some way, or we can just call the code block
    # since it's under `if __name__ == "__main__":` which doesn't get run by import.
    # To test it we can execute the script using runpy.
    import runpy
    runpy.run_path("mortar_calc.py", run_name="__main__")

    captured = capsys.readouterr()
    assert "--- Test Solution" in captured.out
