"""rio_viz.algorithm DEM."""

import numpy
from rio_tiler.colormap import apply_cmap, cmap
from rio_tiler.models import ImageData
from rio_tiler.utils import linear_rescale

from rio_viz.algorithm.base import BaseAlgorithm


class HillShade(BaseAlgorithm):
    """Hillshade."""

    azimuth: int = 90
    angle_altitude: float = 90

    input_nbands: int = 1

    output_nbands: int = 1
    output_dtype: str = "uint8"

    def apply(self, img: ImageData) -> ImageData:
        """Create hillshade from DEM dataset."""
        data = img.data[0]
        mask = img.mask

        x, y = numpy.gradient(data)

        slope = numpy.pi / 2.0 - numpy.arctan(numpy.sqrt(x * x + y * y))
        aspect = numpy.arctan2(-x, y)
        azimuthrad = self.azimuth * numpy.pi / 180.0
        altituderad = self.angle_altitude * numpy.pi / 180.0
        shaded = numpy.sin(altituderad) * numpy.sin(slope) + numpy.cos(
            altituderad
        ) * numpy.cos(slope) * numpy.cos(azimuthrad - aspect)
        hillshade_array = 255 * (shaded + 1) / 2

        # ImageData only accept image in form of (count, height, width)
        arr = numpy.expand_dims(hillshade_array, axis=0).astype(dtype=numpy.uint8)

        return ImageData(
            arr,
            mask,
            assets=img.assets,
            crs=img.crs,
            bounds=img.bounds,
        )


class Contours(BaseAlgorithm):
    """Contours.

    Original idea from https://custom-scripts.sentinel-hub.com/dem/contour-lines/
    """

    increment: int = 35
    thickness: int = 1
    minz: int = -12000
    maxz: int = 8000

    input_nbands: int = 1

    output_nbands: int = 3
    output_dtype: str = "uint8"

    def apply(self, img: ImageData) -> ImageData:
        """Add contours."""
        data = img.data

        # Apply rescaling for minz,maxz to 1->255 and apply Terrain colormap
        arr = linear_rescale(data, (self.minz, self.maxz), (1, 255)).astype("uint8")
        arr, _ = apply_cmap(arr, cmap.get("terrain"))

        # set black (0) for contour lines
        arr = numpy.where(data % self.increment < self.thickness, 0, arr)

        return ImageData(
            arr,
            img.mask,
            assets=img.assets,
            crs=img.crs,
            bounds=img.bounds,
        )
