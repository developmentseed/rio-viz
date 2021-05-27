"""test rio-viz enums."""

import pytest

from rio_viz.resources.enums import TileType


@pytest.mark.parametrize(
    "value,driver,mimetype",
    [
        ("png", "PNG", "image/png"),
        ("npy", "NPY", "application/x-binary"),
        ("tif", "GTiff", "image/tiff; application=geotiff"),
        ("jpeg", "JPEG", "image/jpeg"),
        ("jp2", "JP2OpenJPEG", "image/jp2"),
        ("webp", "WEBP", "image/webp"),
        ("pngraw", "PNG", "image/png"),
        ("pbf", "", "application/x-protobuf"),
        ("mvt", "", "application/x-protobuf"),
    ],
)
def test_tiletype(value, driver, mimetype):
    """Test driver and mimetype values."""
    assert TileType[value].driver == driver
    assert TileType[value].mediatype == mimetype
