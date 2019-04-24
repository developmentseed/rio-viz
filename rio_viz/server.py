"""rio_viz.server: tornado tile server and template renderer."""

from typing import Tuple
from typing.io import BinaryIO

import os
import re
import json
import logging
from io import BytesIO
from concurrent import futures

import numpy

from rio_tiler.utils import array_to_image, linear_rescale, get_colormap
from rio_tiler.profiles import img_profiles

from tornado import web
from tornado import gen
from tornado.ioloop import IOLoop
from tornado.httpserver import HTTPServer
from tornado.concurrent import run_on_executor


logger = logging.getLogger(__name__)


class TileServer(object):
    """Creates a very minimal slippy map tile server using tornado.ioloop."""

    def __init__(
        self, raster, token: str = None, style: str = "satellite", port: int = 8080
    ):
        """Initialize Tornado app."""
        self.raster = raster
        self.port = port
        self.server = None

        tile_params = dict(raster=self.raster)
        tilejson_params = dict(
            raster=self.raster, endpoint=f"http://127.0.0.1:{self.port}"
        )
        template_params = dict(
            endpoint=self.get_endpoint_url(),
            token=token,
            src_path=self.raster.path,
            style=style,
        )

        self.app = web.Application(
            [
                (r"^/(\d+)/(\d+)/(\d+)\.png", RasterTileHandler, tile_params),
                (r"^/(\d+)/(\d+)/(\d+)\.pbf", MVTileHandler, tile_params),
                (r"^/metadata", MetadataHandler, tile_params),
                (r"^/tilejson.json", TileJSONHandler, tilejson_params),
                (r"^/point", PointHandler, tile_params),
                (r"^/index.html", IndexTemplate, template_params),
                (r"/.*", InvalidAddress),
            ]
        )

    def get_endpoint_url(self) -> str:
        """Get endpoint url."""
        return "http://127.0.0.1:{}".format(self.port)

    def get_template_url(self) -> str:
        """Get simple app template url."""
        return "http://127.0.0.1:{}/index.html".format(self.port)

    def get_bounds(self) -> str:
        """Get RasterTiles bounds."""
        return self.raster.bounds

    def get_center(self) -> Tuple:
        """Get RasterTiles center."""
        return self.raster.center

    def start(self):
        """Start tile server."""
        is_running = IOLoop.initialized()
        self.server = HTTPServer(self.app)
        self.server.listen(self.port)

        # NOTE: Check if there is already one server in place
        # else initiate an new one
        # When using rio-glui.server.TileServer inside
        # jupyter Notebook IOLoop is already initialized
        if not is_running:
            IOLoop.current().start()

    def stop(self):
        """Stop tile server."""
        if self.server:
            self.server.stop()


class InvalidAddress(web.RequestHandler):
    """Invalid web requests handler."""

    def get(self):
        """Retunrs 404 error."""
        raise web.HTTPError(404)


class RasterTileHandler(web.RequestHandler):
    """RasterTiles requests handler."""

    executor = futures.ThreadPoolExecutor(max_workers=16)

    def initialize(self, raster):
        """Initialize tiles handler."""
        self.raster = raster

    @run_on_executor
    def _get_tile(
        self,
        z: int,
        x: int,
        y: int,
        indexes: str = None,
        rescale: str = None,
        color_map: str = None,
    ) -> BinaryIO:
        if not self.raster.tile_exists(z, x, y):
            raise web.HTTPError(404)

        if indexes:
            indexes = tuple(int(s) for s in re.findall(r"\d+", indexes))

        tile, mask = self.raster.read_tile(z, x, y, indexes=indexes)

        if rescale:
            rescale_arr = (tuple(map(float, rescale.split(","))),) * tile.shape[0]
            for bdx in range(tile.shape[0]):
                tile[bdx] = numpy.where(
                    mask,
                    linear_rescale(
                        tile[bdx], in_range=rescale_arr[bdx], out_range=[0, 255]
                    ),
                    0,
                )
            tile = tile.astype(numpy.uint8)

        if color_map:
            color_map = get_colormap(color_map, format="gdal")

        options = img_profiles.get("png", {})
        return BytesIO(
            array_to_image(tile, mask, img_format="png", color_map=color_map, **options)
        )

    @gen.coroutine
    def get(self, z: int, x: int, y: int):
        """Retunrs tile data and header."""
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET")
        self.set_header("Content-Type", "image/png")
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate")
        indexes = self.get_argument("indexes", None)
        rescale = self.get_argument("rescale", None)
        color_map = self.get_argument("color_map", None)

        res = yield self._get_tile(
            int(z),
            int(x),
            int(y),
            indexes=indexes,
            rescale=rescale,
            color_map=color_map,
        )
        self.write(res.getvalue())


class MVTileHandler(web.RequestHandler):
    """MVTileHandler requests handler."""

    executor = futures.ThreadPoolExecutor(max_workers=50)

    def initialize(self, raster):
        """Initialize tiles handler."""
        self.raster = raster

    @run_on_executor
    def _get_tile(
        self, z: int, x: int, y: int, feature_type: str = "point"
    ) -> BinaryIO:
        if not self.raster.tile_exists(z, x, y):
            raise web.HTTPError(404)
        return self.raster.read_tile_mvt(z, x, y, feature_type=feature_type)

    @gen.coroutine
    def get(self, z: int, x: int, y: int):
        """Returns tile data and header."""
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET")
        self.set_header("Content-Type", "application/x-protobuf")
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate")
        feature_type = self.get_argument("feature_type", None)
        res = yield self._get_tile(int(z), int(x), int(y), feature_type=feature_type)
        self.write(res)


class MetadataHandler(web.RequestHandler):
    """MetadataHandler requests handler."""

    def initialize(self, raster):
        """Initialize tiles handler."""
        self.raster = raster

    def get(self):
        """Retunrs tile data and header."""
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET")
        self.set_header("Content-Type", "application/json")
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate")
        querystring = self.request.arguments
        params = {}
        for k, v in querystring.items():
            v = str(v[0].decode())
            params[k] = v
        self.write(json.dumps(self.raster.metadata(**params)))


class TileJSONHandler(web.RequestHandler):
    """TileJSONHandler requests handler."""

    def initialize(self, raster, endpoint):
        """Initialize tiles handler."""
        self.raster = raster
        self.endpoint = endpoint

    def get(self):
        """Retunrs tile data and header."""
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET")
        self.set_header("Content-Type", "application/json")
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate")
        tile_format = self.get_argument("tile_format", None)
        querystring = self.request.arguments
        querystring.pop("tile_format")

        tile_url = f"{self.endpoint}/{{z}}/{{x}}/{{y}}.{tile_format}"
        qs = []
        for k, v in querystring.items():
            v = str(v[0].decode())
            qs.append(f"{k}={v}")

        if qs:
            qs = "&".join(qs)
            tile_url += f"?{qs}"

        minzoom = self.raster.minzoom
        maxzoom = self.raster.maxzoom

        meta = dict(
            bounds=self.raster.bounds,
            center=self.raster.center,
            minzoom=minzoom,
            maxzoom=maxzoom,
            name=self.raster.layer_name,
            tilejson="2.1.0",
            tiles=[tile_url],
        )
        self.write(json.dumps(meta))


class PointHandler(web.RequestHandler):
    """PointHandler requests handler."""

    def initialize(self, raster):
        """Initialize tiles handler."""
        self.raster = raster

    def get(self):
        """Retunrs tile data and header."""
        self.set_header("Access-Control-Allow-Origin", "*")
        self.set_header("Access-Control-Allow-Methods", "GET")
        self.set_header("Content-Type", "application/json")
        self.set_header("Cache-Control", "no-store, no-cache, must-revalidate")

        coordinates = self.get_argument("coordinates", None)
        if not coordinates:
            raise web.HTTPError(404)

        indexes = self.get_argument("indexes", None)
        if indexes:
            indexes = tuple(int(s) for s in re.findall(r"\d+", indexes))

        coordinates = list(map(float, coordinates.split(",")))
        self.write(json.dumps(self.raster.point(coordinates, indexes=indexes)))


class Template(web.RequestHandler):
    """Template requests handler."""

    def initialize(
        self,
        src_path: str = None,
        endpoint: str = None,
        token: str = None,
        style: str = "satellite",
    ):
        """Initialize template handler."""
        self.endpoint = endpoint
        self.token = token
        self.src_path = src_path
        self.style = style


class IndexTemplate(Template):
    """Index template."""

    def get(self):
        """Get template."""
        params = dict(
            endpoint=self.endpoint,
            token=self.token,
            layername=os.path.basename(self.src_path),
            mapbox_style=self.style,
        )
        self.render("templates/index.html", **params)
