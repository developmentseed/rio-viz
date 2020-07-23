"""tests rio_viz.server."""

import os
import pytest

from starlette.testclient import TestClient

from rio_viz.raster import RasterTiles
from rio_viz.app import viz

from rio_tiler.errors import TileOutsideBounds


cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")


def test_viz():
    """Should work as expected (create TileServer object)."""
    r = RasterTiles(cog_path)
    app = viz(r)
    assert app.raster == r
    assert app.port == 8080
    assert app.get_bounds() == r.bounds
    assert app.get_center() == r.center
    assert app.get_endpoint_url() == "http://127.0.0.1:8080"
    assert app.get_template_url() == "http://127.0.0.1:8080/index.html"
    assert app.get_simple_template_url() == "http://127.0.0.1:8080/index_simple.html"
    client = TestClient(app.app)

    response = client.get("/")
    assert response.status_code == 404

    response = client.get("/index.html")
    assert response.status_code == 200

    response = client.get("/index_simple.html")
    assert response.status_code == 200

    response = client.get("/tiles/7/64/43.png?rescale=1,10")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get("/tiles/7/64/43.png?rescale=1,10&indexes=1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get("/tiles/7/64/43.png?rescale=1,10&color_map=cfastie")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get("/tiles/7/64/43?rescale=1,10&color_map=cfastie")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    with pytest.raises(TileOutsideBounds):
        client.get("/tiles/18/8624/119094.png")

    with pytest.raises(TileOutsideBounds):
        client.get("/tiles/18/8624/119094.pbf")

    response = client.get("/tiles/7/64/43.pbf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-protobuf"

    response = client.get("/tiles/7/64/43.pbf?feature_type=polygon")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-protobuf"

    response = client.get("/metadata")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    response = client.get("/tilejson.json?tile_format=png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    r = response.json()
    assert r["bounds"]
    assert r["center"]
    assert r["minzoom"] == 6
    assert r["maxzoom"] == 8
    assert r["tiles"][0].endswith("png")

    response = client.get("/tilejson.json?tile_format=pbf")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    r = response.json()
    assert r["tiles"][0].endswith("pbf")

    response = client.get("/tilejson.json?tile_format=pbf&feature_type=polygon")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    r = response.json()
    assert r["tiles"][0].endswith("pbf?feature_type=polygon")

    response = client.get("/point?coordinates=-2,48")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json() == {"coordinates": [-2.0, 48.0], "value": {"band1": 110}}


def test_viz_custom():
    """Should work as expected (create TileServer object)."""
    r = RasterTiles(cog_path)
    app = viz(r, host="0.0.0.0", port=5050)
    assert app.raster == r
    assert app.port == 5050
    assert app.get_bounds() == r.bounds
    assert app.get_center() == r.center
    assert app.get_endpoint_url() == "http://0.0.0.0:5050"
