"""tests rio_viz.server."""

import os
import json

from tornado.testing import AsyncHTTPTestCase

from rio_viz.raster import RasterTiles
from rio_viz.server import TileServer

cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")


def test_TileServer_default():
    """Should work as expected (create TileServer object)."""
    r = RasterTiles(cog_path)
    app = TileServer(r)
    assert app.raster == r
    assert app.port == 8080
    assert not app.server
    assert app.get_bounds() == r.bounds
    assert app.get_center() == r.center
    assert app.get_endpoint_url() == "http://127.0.0.1:8080"
    assert app.get_template_url() == "http://127.0.0.1:8080/index.html"


class TestHandlers(AsyncHTTPTestCase):
    """Test tornado handlers."""

    def get_app(self):
        """Initialize app."""
        r = RasterTiles(cog_path)
        return TileServer(r).app

    def test_get_root(self):
        """Should return error on root query."""
        response = self.fetch("/")
        self.assertEqual(response.code, 404)

    def test_tile(self):
        """Should return tile buffer."""
        response = self.fetch("/7/64/43.png?rescale=1,10")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "image/png")

    def test_indexes(self):
        """Should return tile buffer."""
        response = self.fetch("/7/64/43.png?rescale=1,10&indexes=1")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "image/png")

    def test_cmap(self):
        """Should return tile buffer."""
        response = self.fetch("/7/64/43.png?rescale=1,10&color_map=cfastie")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "image/png")

    def test_tileNotFound(self):
        """Should error with tile doesn't exits."""
        response = self.fetch("/18/8624/119094.png")
        self.assertEqual(response.code, 404)

    def test_tileMVTNotFound(self):
        """Should error with tile doesn't exits."""
        response = self.fetch("/18/8624/119094.pbf")
        self.assertEqual(response.code, 404)

    def test_tileMVT(self):
        """Should return tile buffer."""
        response = self.fetch("/7/64/43.pbf")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "application/x-protobuf")

    def test_tileMVTp(self):
        """Should return tile buffer."""
        response = self.fetch("/7/64/43.pbf?feature_type=polygon")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "application/x-protobuf")

    def test_metadata(self):
        """Should return image metadata."""
        response = self.fetch("/metadata")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "application/json")

    def test_metadataBins(self):
        """Should return image metadata."""
        response = self.fetch("/metadata?histogram_bins=10")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "application/json")

    def test_tileJSON(self):
        """Should return tilejson."""
        response = self.fetch("/tilejson.json?tile_format=png")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        res = json.load(response.buffer)
        assert res["bounds"]
        assert res["center"]
        assert res["minzoom"] == 6
        assert res["maxzoom"] == 8
        assert res["name"] == "cog.tif"
        assert res["tiles"]
        assert res["tiles"][0].endswith("png")

        response = self.fetch("/tilejson.json?tile_format=pbf")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        res = json.load(response.buffer)
        assert res["tiles"][0].endswith("pbf")

        response = self.fetch("/tilejson.json?tile_format=pbf&feature_type=polygon")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        res = json.load(response.buffer)
        assert res["tiles"][0].endswith("pbf?feature_type=polygon")

    def test_Point(self):
        """Should return point value."""
        response = self.fetch("/point?coordinates=-2,48&indexes=1")
        self.assertEqual(response.code, 200)
        self.assertTrue(response.buffer)
        self.assertEqual(response.headers["Content-Type"], "application/json")
        res = json.load(response.buffer)
        assert res == {"coordinates": [-2.0, 48.0], "value": {"cog_band1": 110}}
