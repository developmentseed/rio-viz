"""tests rio_viz.server."""

import json
import os

import pytest
from rio_tiler.errors import TileOutsideBounds
from rio_tiler.io import COGReader
from starlette.testclient import TestClient

from rio_viz.app import viz
from rio_viz.compat import AsyncReader
from rio_viz.io.reader import MultiFilesReader

cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")
cogb1b2b3_path = os.path.join(os.path.dirname(__file__), "fixtures", "cogb{1,2,3}.tif")


def test_viz():
    """Should work as expected (create TileServer object)."""
    src_path = cog_path
    dataset_reader = type("AsyncReader", (AsyncReader,), {"reader": COGReader})

    app = viz(src_path, reader=dataset_reader)

    assert app.port == 8080
    assert app.endpoint == "http://127.0.0.1:8080"
    assert app.template_url == "http://127.0.0.1:8080/index.html"

    client = TestClient(app.app)
    response = client.get("/")
    assert response.status_code == 404

    response = client.get("/index.html")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-cache"

    response = client.get("/tiles/7/64/43.png?rescale=1,10")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["cache-control"] == "no-cache"

    response = client.get(
        "/tiles/7/64/43.png?rescale=1,10&bidx=1&color_formula=Gamma R 3"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get("/tiles/7/64/43.png?rescale=1,10&bidx=1&bidx=1&bidx=1")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get("/tiles/7/64/43.png?rescale=1,10&colormap_name=cfastie")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get("/tiles/7/64/43?rescale=1,10&colormap_name=cfastie")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    with pytest.raises(TileOutsideBounds):
        client.get("/tiles/18/8624/119094.png")

    with pytest.raises(TileOutsideBounds):
        client.get("/tiles/18/8624/119094.pbf")

    response = client.get("/tiles/7/64/43.pbf")
    assert response.status_code == 500
    assert not response.headers.get("cache-control")

    response = client.get("/tiles/7/64/43.pbf?feature_type=polygon")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-protobuf"

    response = client.get("/tiles/7/64/43.pbf?feature_type=point")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-protobuf"

    response = client.get("/preview?rescale=1,10&colormap_name=cfastie")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["cache-control"] == "no-cache"

    response = client.get("/preview.png?rescale=1,10&colormap_name=cfastie")
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get(
        "/crop/-2.00,48.5,-1,49.5.png?rescale=1,10&colormap_name=cfastie"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.get(
        "/crop/-2.00,48.5,-1,49.5/100x100.jpeg?&rescale=1,10&colormap_name=cfastie"
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

    response = client.get("/info")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    response = client.get("/metadata")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"

    response = client.get("/tilejson.json?tile_format=png")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    r = response.json()
    assert r["bounds"]
    assert r["center"]
    assert r["minzoom"] == 7
    assert r["maxzoom"] == 9
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
    assert response.json() == {"coordinates": [-2.0, 48.0], "value": [110]}

    feat = json.dumps(
        {
            "type": "Feature",
            "properties": {},
            "geometry": {
                "type": "Polygon",
                "coordinates": [
                    [
                        [-1.8511962890624998, 49.296471602658066],
                        [-2.5213623046875, 48.56388521347092],
                        [-2.1258544921875, 48.213692646648035],
                        [-1.4556884765625, 48.356249029540734],
                        [-1.1590576171875, 48.469279317167164],
                        [-0.8184814453125, 49.46455408928758],
                        [-1.4666748046875, 49.55728898983402],
                        [-1.64794921875, 49.50380954152213],
                        [-1.8511962890624998, 49.296471602658066],
                    ]
                ],
            },
        }
    )

    response = client.post("/crop", data=feat)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"

    response = client.post("/crop.jpeg", data=feat)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

    response = client.post("/crop/100x100.jpeg", data=feat)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"

    response = client.post(
        "/crop.jpeg",
        params={"bidx": 1, "rescale": "1,10", "colormap_name": "cfastie"},
        data=feat,
    )
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"


def test_viz_custom():
    """Should work as expected (create TileServer object)."""
    src_path = cog_path
    dataset_reader = type("AsyncReader", (AsyncReader,), {"reader": COGReader})

    app = viz(src_path, reader=dataset_reader, host="0.0.0.0", port=5050)
    assert app.port == 5050
    assert app.endpoint == "http://0.0.0.0:5050"


def test_viz_multi():
    """Should work as expected (create TileServer object)."""
    src_path = cogb1b2b3_path
    dataset_reader = type("AsyncReader", (AsyncReader,), {"reader": MultiFilesReader})

    app = viz(src_path, reader=dataset_reader)
    assert app.port == 8080
    assert app.endpoint == "http://127.0.0.1:8080"
    client = TestClient(app.app)

    response = client.get("/info")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/json"
    assert response.json()["band_descriptions"] == [
        ["file1", ""],
        ["file2", ""],
        ["file3", ""],
    ]
