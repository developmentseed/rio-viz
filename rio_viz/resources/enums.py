"""Titiler Enums."""

from enum import Enum
from types import DynamicClassAttribute

from rasterio.enums import Resampling

from rio_tiler.colormap import cmap
from rio_tiler.profiles import img_profiles


class MimeTypes(str, Enum):
    """MineTypes."""

    tif = "image/tiff; application=geotiff"
    jp2 = "image/jp2"
    png = "image/png"
    pngraw = "image/png"
    jpeg = "image/jpeg"
    webp = "image/webp"
    npy = "application/x-binary"
    pbf = "application/x-protobuf"
    mvt = "application/x-protobuf"
    xml = "application/xml"
    json = "application/json"
    html = "text/html"
    text = "text/plain"


class ImageDrivers(str, Enum):
    """Rio-tiler supported output drivers."""

    jpeg = "JPEG"
    png = "PNG"
    pngraw = "PNG"
    tif = "GTiff"
    webp = "WEBP"
    jp2 = "JP2OpenJPEG"
    npy = "NPY"


class ImageType(Enum):
    """Available Output Image type."""

    png = "png"
    npy = "npy"
    tif = "tif"
    jpeg = "jpg"
    jp2 = "jp2"
    webp = "webp"
    pngraw = "pngraw"

    @DynamicClassAttribute
    def profile(self):
        """Return rio-tiler image default profile."""
        return img_profiles.get(self._name_, {})

    @DynamicClassAttribute
    def driver(self):
        """Return rio-tiler image default profile."""
        return ImageDrivers[self._name_].value

    @DynamicClassAttribute
    def mimetype(self):
        """Return image mimetype."""
        return MimeTypes[self._name_].value


class TileType(Enum):
    """Available Output Tile type."""

    png = "png"
    npy = "npy"
    tif = "tif"
    jpeg = "jpg"
    jp2 = "jp2"
    webp = "webp"
    pngraw = "pngraw"
    pbf = "pbf"
    mvt = "mvt"

    @DynamicClassAttribute
    def profile(self):
        """Return rio-tiler image default profile."""
        return img_profiles.get(self._name_, {})

    @DynamicClassAttribute
    def driver(self):
        """Return rio-tiler image default profile."""
        try:
            return ImageDrivers[self._name_].value
        except KeyError:
            return ""

    @DynamicClassAttribute
    def mimetype(self):
        """Return image mimetype."""
        return MimeTypes[self._name_].value


class ColormapEnumFactory(Enum):
    """Rio-Tiler colormaps."""

    @DynamicClassAttribute
    def data(self):
        """Return rio-tiler image default profile."""
        return cmap.get(self._name_)


ColorMaps = ColormapEnumFactory(  # type: ignore
    "ColorMaps", [(a, a) for a in sorted(cmap.list())]
)

ResamplingNames = Enum(  # type: ignore
    "ResamplingNames", [(r.name, r.name) for r in Resampling]
)
