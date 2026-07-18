"""
test_coordinate_conversion_pixel.py - Unit tests for coordinate_conversion_pixel.py
"""

from src.coordinate_conversion_pixel import convert_bng_to_utm, utm_coordinate_to_pixel


# --- convert_bng_to_utm tests ---
def test_convert_bng_to_utm_returns_dict():
    """
    Tests that convert_bng_to_utm returns a dictionary.
    """
    result = convert_bng_to_utm(388309.18, 344107.34)
    assert isinstance(result, dict)


def test_convert_bng_to_utm_returns_correct_keys():
    """
    Tests that the returned dict contains x and y keys.
    """
    result = convert_bng_to_utm(388309.18, 344107.34)
    assert "x" in result
    assert "y" in result


def test_convert_bng_to_utm_known_values():
    """
    Tests that convert_bng_to_utm produces correct UTM values against
    a known conversion verified in 02_brownfield_register_eda.ipynb.
    """
    result = convert_bng_to_utm(388309.18, 344107.34)
    assert abs(result["x"] - 555331.19) < 1.0
    assert abs(result["y"] - 5871939.23) < 1.0


# --- utm_coordinate_to_pixel tests ---
def test_utm_coordinate_to_pixel_returns_dict():
    """
    Tests that utm_coordinate_to_pixel returns a dictionary.
    """
    tile_metadata = {"left": 499980, "top": 5900040, "resolution": 20}
    result = utm_coordinate_to_pixel(555331.19, 5871939.23, tile_metadata)
    assert isinstance(result, dict)


def test_utm_coordinate_to_pixel_returns_correct_keys():
    """
    Tests that the returned dict contains row and column keys.
    """
    tile_metadata = {"left": 499980, "top": 5900040, "resolution": 20}
    result = utm_coordinate_to_pixel(555331.19, 5871939.23, tile_metadata)
    assert "row" in result
    assert "column" in result


def test_utm_coordinate_to_pixel_correct_values():
    """
    Tests that utm_coordinate_to_pixel produces correct pixel positions
    using known tile metadata and a known UTM coordinate.
    """
    tile_metadata = {"left": 499980, "top": 5900040, "resolution": 20}
    result = utm_coordinate_to_pixel(555331.19, 5871939.23, tile_metadata)
    assert result["column"] == int((555331.19 - 499980) / 20)
    assert result["row"] == int((5900040 - 5871939.23) / 20)


def test_utm_coordinate_to_pixel_returns_integers():
    """
    Tests that row and column values are integers, not floats.
    """
    tile_metadata = {"left": 499980, "top": 5900040, "resolution": 20}
    result = utm_coordinate_to_pixel(555331.19, 5871939.23, tile_metadata)
    assert isinstance(result["row"], int)
    assert isinstance(result["column"], int)  #


def test_convert_bng_to_utm_zero_coordinates():
    """Tests convert_bng_to_utm handles zero coordinates."""
    result = convert_bng_to_utm(0.0, 0.0)
    assert isinstance(result, dict)
    assert "x" in result
    assert "y" in result


def test_convert_bng_to_utm_returns_floats():
    """Tests that returned UTM coordinates are floats."""
    result = convert_bng_to_utm(388309.18, 344107.34)
    assert isinstance(result["x"], float)
    assert isinstance(result["y"], float)


def test_utm_coordinate_to_pixel_different_resolution():
    """Tests utm_coordinate_to_pixel with 10m resolution."""
    tile_metadata = {"left": 499980, "top": 5900040, "resolution": 10}
    result = utm_coordinate_to_pixel(555331.19, 5871939.23, tile_metadata)
    assert result["column"] == int((555331.19 - 499980) / 10)
    assert result["row"] == int((5900040 - 5871939.23) / 10)


def test_utm_coordinate_to_pixel_at_tile_origin():
    """Tests that a coordinate at the tile origin returns row=0, column=0."""
    tile_metadata = {"left": 499980, "top": 5900040, "resolution": 20}
    result = utm_coordinate_to_pixel(499980.0, 5900040.0, tile_metadata)
    assert result["row"] == 0
    assert result["column"] == 0


def test_utm_coordinate_to_pixel_negative_column():
    """Tests that a coordinate west of the tile returns negative column."""
    tile_metadata = {"left": 499980, "top": 5900040, "resolution": 20}
    result = utm_coordinate_to_pixel(400000.0, 5871939.23, tile_metadata)
    assert result["column"] < 0
