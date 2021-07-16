"""rio-viz app dependencies."""

from dataclasses import dataclass, field
from typing import List, Optional

from fastapi import Query

from titiler.core.dependencies import DefaultDependency


# Dependencies for simple BaseReader
@dataclass
class IndexesParams(DefaultDependency):
    """Band Indexes parameters."""

    bidx: Optional[List[int]] = Query(
        None, title="Band indexes", description="band indexes",
    )

    def __post_init__(self):
        """Post Init."""
        if self.bidx is not None:
            self.kwargs["indexes"] = self.bidx


# Dependencies for  MultiBaseReader
@dataclass
class AssetsParams(DefaultDependency):
    """Asset and Band indexes parameters."""

    asset: Optional[List[str]] = Query(
        None, title="Asset indexes", description="asset names."
    )

    default_assets: Optional[List[str]] = field(init=False)

    def __post_init__(self):
        """Post Init."""
        if self.asset or self.default_assets:
            self.kwargs["assets"] = self.asset or self.default_assets


# Dependencies for  MultiBandReader
@dataclass
class BandsParams(DefaultDependency):
    """Band names parameters."""

    band: Optional[List[str]] = Query(
        None, title="bands names", description="bands names.",
    )

    default_bands: Optional[List[str]] = field(init=False)

    def __post_init__(self):
        """Post Init."""
        if self.band or self.default_bands:
            self.kwargs["bands"] = self.band or self.default_bands
