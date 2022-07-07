"""rio_viz.algorithm."""

from typing import Dict, Type

from rio_viz.algorithm.base import AlgorithmMetadata, BaseAlgorithm  # noqa
from rio_viz.algorithm.dem import Contours, HillShade
from rio_viz.algorithm.index import NormalizedIndex

AVAILABLE_ALGORITHM: Dict[str, Type[BaseAlgorithm]] = {
    "hillshade": HillShade,
    "contours": Contours,
    "normalizedIndex": NormalizedIndex,
}
