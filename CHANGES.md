# 0.14.0 (2025-03-20)

* add `--geojson` option to add a GeoJSON Feature or FeatureCollection on the map viewer

# 0.13.1 (2025-03-19)

* relaxe titiler requirement to `>=0.20,<0.22`

# 0.13.0 (2025-01-20)

* remove python 3.8 support
* update titiler dependency to `>=0.20,<0.21`
* remove docker image publishing

# 0.12.2 (2024-04-24)

* update titiler dependency to `>=0.16,<0.19`
* add python 3.12 official support
* change code formatter to `ruff-format`
* switch to Hatch

# 0.12.1 (2024-01-12)

* fix invalid nodata overwriting

# 0.12.0 (2024-01-12)

* add Algorithm support and update basemap source
* update titiler requirement to `>=0.16,<0.17`

- renamed `/crop` endpoints to `/bbox/...` or `/feature/...`
  - `/crop/{minx},{miny},{maxx},{maxy}.{format}` -> `/bbox/{minx},{miny},{maxx},{maxy}.{format}`

  - `/crop/{minx},{miny},{maxx},{maxy}/{width}x{height}.{format}` -> `/bbox/{minx},{miny},{maxx},{maxy}/{width}x{height}.{format}`

  - `/crop [POST]` -> `/feature [POST]`

  - `/crop.{format} [POST]` -> `/feature.{format} [POST]`

  - `/crop/{width}x{height}.{format}  [POST]` -> `/feature/{width}x{height}.{format} [POST]`


# 0.11.0 (2023-07-27)

* update titiler requirement to `>=0.13,<0.14`

# 0.10.3 (2023-03-22)

* switch `/map` viewer to maplibre

## 0.10.2 (2023-03-20)

* handle dateline crossing dataset in html viewers
* fix issue with FastAPI>0.93
* update FastAPI dependency version

## 0.10.1 (2023-03-01)

* update titiler requirement

## 0.10.0 (2022-12-16)

* remove `AsyncBaseReader` support
* add Jupyter Notebook compatible `Client`

```python
import time

import httpx
from folium import Map, TileLayer

from rio_viz.app import Client

# Create rio-viz Client (using server-thread to launch background task)
client = Client("https://data.geo.admin.ch/ch.swisstopo.swissalti3d/swissalti3d_2019_2573-1085/swissalti3d_2019_2573-1085_0.5_2056_5728.tif")

# Gives some time for the server to setup
time.sleep(1)

r = httpx.get(
    f"{client.endpoint}/tilejson.json",
    params = {
        "rescale": "1600,2000",  # from the info endpoint
        "colormap_name": "terrain",
    }
).json()

bounds = r["bounds"]
m = Map(
    location=((bounds[1] + bounds[3]) / 2,(bounds[0] + bounds[2]) / 2),
    zoom_start=r["minzoom"]
)

aod_layer = TileLayer(
    tiles=r["tiles"][0],
    opacity=1,
    attr="Yo!!"
)
aod_layer.add_to(m)
m
```

* update `rio-tiler-mvt` requirement (**>=0.1,<0.2**)

* add support for python 3.10 and 3.11
* remove python 3.7 support
* update titiler requirement to `0.10`
* revert using static files for javascript libraries
* add simple `/map` viewer

## 0.9.6 (2022-06-14)

* update `titiler` and `starlette-cramjam` requirements

## 0.9.5 (2022-05-17)

* Fix viewers. Statistics wasn't being displayed for raster with band names (instead of indexes number).

## 0.9.4 (2022-05-16)

* fix issue for MultiBaseReader (`assets`) viewer
* update titiler.core requirement to `>=0.5,<0.7`
* add `/` as path for the viewer

## 0.9.3 (2022-04-01)

* fix frontend click/point interaction for dataset crossing the antimeridian line

## 0.9.2 (2022-03-29)

* better handle data with bbox crossing the antimeridian limit
* include js and css code within the package to enable full offline mode
* switch to pyproject.toml

## 0.9.1 (2022-02-25)

* add `color-formula` in viz

## 0.9.0 (2022-02-25)

* update titiler requirement and fix viewer bugs

## 0.8.0 (2021-11-30)

* update to new titiler/rio-tiler/rio-cogeo version
* remove Mapbox maps and switch to `stamen` basemap
* remove python3.6 support

## 0.7.2 (2021-09-23)

* use titiler custom JSONResponse to encode nan/inf/-inf values in response

## 0.7.1 (2021-09-17)

* do not rescale data if there is a colormap

## 0.7.0 (2021-07-16)

* add `titiler.core` as dependencies to reduce code duplication.
* update code and templates to follow `titiler.core` specs.
* add `/crop.{format}` POST endpoint to get image from polygon shaped GeoJSON (https://github.com/developmentseed/rio-viz/pull/36)
* rename `/part` to `/crop` to match TiTiler (https://github.com/developmentseed/rio-viz/pull/36)
* refactor dependencies to remove bidx in info/metadata/stats (https://github.com/developmentseed/rio-viz/pull/37)
* refactor UI (https://github.com/developmentseed/rio-viz/pull/38)
* add simple **MosaicReader** (https://github.com/developmentseed/rio-viz/pull/32)

    ```bash
    $ rio viz "tests/fixtures/mosaic_cog{1,2}.tif" --reader rio_viz.io.MosaicReader
    ```

## 0.6.1 (2021-04-08)

* update rio-tiler-mvt
* use cache middleware to add `cache-control` headers.

## 0.6.0 (2021-03-23)

* add dynamic dependency injection to better support multiple reader types (https://github.com/developmentseed/rio-viz/pull/28)
* add better UI for MultiBaseReader (e.g STAC)
* renamed `indexes` query parameter to `bidx`
* update bands/assets/indexes query parameter style to follow the common specification

```
# before
/tiles/9/150/189?indexes=1,2,3

# now
/tiles/9/150/189?bidx=1&bidx=2&bidx=3
```

## 0.5.0 (2021-03-01)

* renamed `rio_viz.ressources` to `rio_viz.resources` (https://github.com/developmentseed/titiler/pull/210)
* update and reduce requirements
* fix wrong tilesize setting in UI
* update pre-commit configuration

## 0.4.4 (2021-01-27)

* update requirements.
* add Mapbox `dark` basemap as default.

## 0.4.3.post1 (2020-12-15)

* add missing `__init__` in rio_viz.io submodule (https://github.com/developmentseed/rio-viz/pull/24)

## 0.4.3 (2020-12-15)

* Fix error when `rio-tiler-mvt` is not installed (https://github.com/developmentseed/rio-viz/issues/21)

## 0.4.2 (2020-11-24)

* update for rio-tiler 2.0.0rc3

## 0.4.1 (2020-11-17)

* add `--server-only` options and add preview/part API.
* add more output types.

## 0.4.0 (2020-11-09)

**Refactor**

* remove template factory
* better FastAPI app definition (to be able to use it outside rio-viz)
* remove `simple` template
* use dataclasses
* adapt for rio-tiler >= 2.0.0rc1
* full async API
* add `external` reader support
