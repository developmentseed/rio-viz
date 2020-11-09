"""Titiler Enums."""

from enum import Enum
from types import DynamicClassAttribute

from rio_tiler.profiles import img_profiles

drivers = dict(jpg="JPEG", png="PNG", tif="GTiff", webp="WEBP")


class ImageType(str, Enum):
    """Image Type Enums."""

    png = "png"
    npy = "npy"
    tif = "tif"
    jpg = "jpg"
    webp = "webp"

    @DynamicClassAttribute
    def profile(self):
        """Return rio-tiler image default profile."""
        return img_profiles.get(self.driver.lower(), {})

    @DynamicClassAttribute
    def driver(self):
        """Return rio-tiler image default profile."""
        return drivers[self._name_]


class VectorType(str, Enum):
    """Vector Type Enums."""

    pbf = "pbf"
    mvt = "mvt"

    @DynamicClassAttribute
    def profile(self):
        """Placeholder."""
        pass

    @DynamicClassAttribute
    def driver(self):
        """Placeholder."""
        pass


class MimeTypes(str, Enum):
    """Image MineTypes."""

    geotiff = "image/tiff; application=geotiff"
    tiff = "image/tiff"
    tif = "image/tiff"
    cog = "image/geo+tiff; application=geotiff; profile=cloud-optimized"
    jp2 = "image/jp2"
    png = "image/png"
    jpeg = "image/jpeg"
    jpg = "image/jpeg"
    webp = "image/webp"
    binnary = "application/x-binary"
    npy = "application/x-binary"
    pbf = "application/x-protobuf"
    mvt = "application/x-protobuf"
    xml = "application/xml"
    json = "application/json"
    html = "text/html"
    text = "text/plain"
