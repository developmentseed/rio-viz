"""tests rio_viz.raster."""

import os
import pytest

from rio_viz.raster import RasterTiles
from rio_tiler.errors import TileOutsideBounds


cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")

cogb1_path = os.path.join(os.path.dirname(__file__), "fixtures", "cogb1.tif")
cogb2_path = os.path.join(os.path.dirname(__file__), "fixtures", "cogb2.tif")
cogb3_path = os.path.join(os.path.dirname(__file__), "fixtures", "cogb3.tif")


def test_rastertiles_valid():
    """Should work as expected (create rastertiles object)."""
    r = RasterTiles(cog_path)
    assert r.path == (cog_path,)
    assert list(map(int, r.bounds)) == [-3, 47, 0, 50]
    assert r.minzoom == 6
    assert r.maxzoom == 8
    assert r.band_descriptions == ["band1"]

    r = RasterTiles(cog_path, minzoom=0)
    assert r.path == (cog_path,)
    assert r.minzoom == 0

    r = RasterTiles((cog_path,))
    assert r.path == (cog_path,)

    r = RasterTiles((cogb1_path, cogb2_path, cogb3_path))
    assert r.path == (cogb1_path, cogb2_path, cogb3_path)
    assert list(map(int, r.bounds)) == [-3, 47, 0, 50]
    assert r.minzoom == 6
    assert r.maxzoom == 8
    assert r.band_descriptions == ["cogb1", "cogb2", "cogb3"]
    assert r.data_type


def test_rastertiles_tile_point_valid():
    """Should work as expected (create rastertiles object and get point value)."""
    r = RasterTiles(cog_path)
    p = r.point([-2, 48])
    assert p == {"coordinates": [-2, 48], "value": {"band1": 110}}

    r = RasterTiles(cog_path)
    p = r.point([-2, 48])
    assert p == {"coordinates": [-2, 48], "value": {"band1": 110}}

    r = RasterTiles((cogb1_path, cogb2_path, cogb3_path))
    p = r.point([-2, 48])
    assert p == {
        "coordinates": [-2, 48],
        "value": {"cogb1": 110, "cogb2": 110, "cogb3": 110},
    }


@pytest.mark.asyncio
async def test_rastertiles_read_tile():
    """Should work as expected (create rastertiles object and read tile)."""
    r = RasterTiles(cog_path)
    z = 7
    x = 63
    y = 43
    data, mask = r.read_tile(z, x, y)
    assert data.shape == (1, 256, 256)
    assert mask.shape == (256, 256)

    data, mask = r.read_tile(z, x, y, tilesize=512, indexes=[1])
    assert data.shape == (1, 512, 512)
    assert mask.shape == (512, 512)

    assert await r.read_tile_mvt(z, x, y)
    assert await r.read_tile_mvt(z, x, y, feature_type="polygon")

    # outside tile
    z = 7
    x = 65
    y = 49
    with pytest.raises(TileOutsideBounds):
        await r.read_tile_mvt(z, x, y)

    with pytest.raises(TileOutsideBounds):
        await r.read_tile_mvt(z, x, y, feature_type="polygon")

    with pytest.raises(TileOutsideBounds):
        r.read_tile(z, x, y)

    # MultipleFiles
    r = RasterTiles((cogb1_path, cogb2_path, cogb3_path))
    z = 7
    x = 63
    y = 43
    data, mask = r.read_tile(z, x, y)
    assert data.shape == (3, 256, 256)
    assert mask.shape == (256, 256)

    data, mask = r.read_tile(z, x, y, tilesize=512, indexes=[1])
    assert data.shape == (1, 512, 512)
    assert mask.shape == (512, 512)

    assert await r.read_tile_mvt(z, x, y)
    assert await r.read_tile_mvt(z, x, y, feature_type="polygon")


@pytest.mark.asyncio
async def test_rastertiles_metadata():
    """Should work as expected (create rastertiles object and get metadata)."""
    r = RasterTiles(cog_path)
    metadata = r.metadata()
    assert metadata["band_descriptions"] == [(1, "band1")]
    assert metadata["bounds"]
    assert metadata["statistics"]
    assert len(metadata["statistics"][1]["histogram"][0]) == 10

    r = RasterTiles((cogb1_path, cogb2_path, cogb3_path))
    metadata = r.metadata()
    assert metadata["band_descriptions"] == [(1, "cogb1"), (2, "cogb2"), (3, "cogb3")]
    assert metadata["bounds"]
    assert metadata["statistics"]
    assert metadata["dtype"]
    assert len(metadata["statistics"].keys()) == 3

    metadata = r.metadata(indexes=(2,))
    assert metadata["band_descriptions"] == [(2, "cogb2")]
    assert metadata["bounds"]
    assert metadata["statistics"]
    assert len(metadata["statistics"].keys()) == 1
