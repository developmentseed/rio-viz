"""rio-viz Enums."""

from enum import Enum
from types import DynamicClassAttribute

from rio_tiler.profiles import img_profiles


class MediaType(str, Enum):
    """Responses Media types formerly known as MIME types."""

    tif = "image/tiff; application=geotiff"
    jp2 = "image/jp2"
    png = "image/png"
    pngraw = "image/png"
    jpeg = "image/jpeg"
    jpg = "image/jpg"
    webp = "image/webp"
    npy = "application/x-binary"
    xml = "application/xml"
    json = "application/json"
    geojson = "application/geo+json"
    html = "text/html"
    text = "text/plain"
    pbf = "application/x-protobuf"
    mvt = "application/x-protobuf"


class ImageDriver(str, Enum):
    """Supported output GDAL drivers."""

    jpeg = "JPEG"
    jpg = "JPEG"
    png = "PNG"
    pngraw = "PNG"
    tif = "GTiff"
    webp = "WEBP"
    jp2 = "JP2OpenJPEG"
    npy = "NPY"


class DataFormat(str, Enum):
    """Data Format Base Class."""

    @DynamicClassAttribute
    def profile(self):
        """Return rio-tiler image default profile."""
        return img_profiles.get(self._name_, {})

    @DynamicClassAttribute
    def driver(self):
        """Return rio-tiler image default profile."""
        try:
            return ImageDriver[self._name_].value
        except KeyError:
            return ""

    @DynamicClassAttribute
    def mediatype(self):
        """Return image mimetype."""
        return MediaType[self._name_].value


class RasterFormat(DataFormat):
    """Available Output Raster format."""

    png = "png"
    npy = "npy"
    tif = "tif"
    jpeg = "jpeg"
    jpg = "jpg"
    jp2 = "jp2"
    webp = "webp"
    pngraw = "pngraw"


class VectorTileFormat(DataFormat):
    """Available Output Vector Tile format."""

    pbf = "pbf"
    mvt = "mvt"
