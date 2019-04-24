"""tests rio_viz.raster."""

import os

from rio_viz.raster import RasterTiles

cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")


def test_rastertiles_valid():
    """Should work as expected (create rastertiles object)."""
    r = RasterTiles(cog_path)
    assert r.path == cog_path
    assert r.layer_name == "cog.tif"
    assert list(map(int, r.bounds)) == [-3, 47, 0, 50]
    assert r.minzoom == 6
    assert r.maxzoom == 8
    assert r.band_descriptions == ["band1"]


# read_tile
# read_tile_mvt
# point
# metadata


def test_rastertiles_tile_exists_valid():
    """Should work as expected (create rastertiles object and check if tile exists)."""
    r = RasterTiles(cog_path)
    z = 7
    x = 64
    y = 43
    assert r.tile_exists(z, x, y)

    z = 7
    x = 4
    y = 43
    assert not r.tile_exists(z, x, y)


def test_rastertiles_tile_point_valid():
    """Should work as expected (create rastertiles object and get point value)."""
    r = RasterTiles(cog_path)
    p = r.point([-2, 48])
    assert p == {"coordinates": [-2, 48], "value": {"band1": 110}}

    r = RasterTiles(cog_path)
    p = r.point([-2, 48], indexes=1)
    assert p == {"coordinates": [-2, 48], "value": {"band1": 110}}


def test_rastertiles_read_tile():
    """Should work as expected (create rastertiles object and read tile)."""
    r = RasterTiles(cog_path)
    # empty tile
    z = 7
    x = 64
    y = 43
    data, mask = r.read_tile(z, x, y)
    assert data.shape == (1, 256, 256)
    assert mask.shape == (256, 256)

    data, mask = r.read_tile(z, x, y, tilesize=512)
    assert data.shape == (1, 512, 512)
    assert mask.shape == (512, 512)

    assert not r.read_tile_mvt(z, x, y)

    z = 7
    x = 63
    y = 43
    assert r.read_tile_mvt(z, x, y)
    assert r.read_tile_mvt(z, x, y, feature_type="polygon")


def test_rastertiles_metadata():
    """Should work as expected (create rastertiles object and get metadata)."""
    r = RasterTiles(cog_path)
    metadata = r.metadata()
    assert metadata["address"]
    assert metadata["bounds"]
    assert metadata["statistics"]
    assert len(metadata["statistics"][1]["histogram"][0]) == 20

    metadata = r.metadata(histogram_bins=10)
    assert len(metadata["statistics"][1]["histogram"][0]) == 10

    metadata = r.metadata(histogram_bins="10")
    assert len(metadata["statistics"][1]["histogram"][0]) == 10

    pc = metadata["statistics"][1]["pc"]
    metadata = r.metadata(histogram_range=pc)
    assert metadata["statistics"][1]["histogram"]

    print(metadata["statistics"][1]["pc"])
    pc = ",".join(list(map(str, metadata["statistics"][1]["pc"])))
    metadata = r.metadata(histogram_range=pc, indexes="1")
    assert metadata["statistics"][1]["histogram"]
