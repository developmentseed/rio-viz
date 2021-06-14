"""test rio-viz enums."""

import pytest

from rio_viz.resources.enums import RasterFormat, VectorTileFormat


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
    ],
)
def test_rasterformat(value, driver, mimetype):
    """Test driver and mimetype values."""
    assert RasterFormat[value].driver == driver
    assert RasterFormat[value].mediatype == mimetype


@pytest.mark.parametrize(
    "value,driver,mimetype",
    [("pbf", "", "application/x-protobuf"), ("mvt", "", "application/x-protobuf")],
)
def test_vectorformat(value, driver, mimetype):
    """Test driver and mimetype values."""
    assert VectorTileFormat[value].driver == driver
    assert VectorTileFormat[value].mediatype == mimetype
