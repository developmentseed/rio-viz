"""Titiler Enums."""

from enum import Enum


class ImageType(str, Enum):
    """Image Type Enums."""

    png = "png"
    npy = "npy"
    jpg = "jpg"


class VectorType(str, Enum):
    """Vector Type Enums."""

    pbf = "pbf"
    mvt = "mvt"
