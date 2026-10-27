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
