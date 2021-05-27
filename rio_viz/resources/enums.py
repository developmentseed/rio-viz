"""rio-viz Enums."""

from enum import Enum
from types import DynamicClassAttribute

from rio_tiler.profiles import img_profiles

from titiler.core.resources.enums import ImageDriver, MediaType


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
            return ImageDriver[self._name_].value
        except KeyError:
            return ""

    @DynamicClassAttribute
    def mediatype(self):
        """Return image mimetype."""
        return MediaType[self._name_].value
