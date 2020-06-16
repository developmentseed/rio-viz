# rio-viz

[![Packaging status](https://badge.fury.io/py/rio-viz.svg)](https://badge.fury.io/py/rio-viz)
[![CircleCI](https://circleci.com/gh/developmentseed/rio-viz.svg?style=svg)](https://circleci.com/gh/developmentseed/rio-viz)
[![codecov](https://codecov.io/gh/developmentseed/rio-viz/branch/master/graph/badge.svg?token=MVVL228Lug)](https://codecov.io/gh/developmentseed/rio-viz)

Rasterio plugin to visualize Cloud Optimized GeoTIFF in browser.

![](https://user-images.githubusercontent.com/10407788/60689165-78be7780-9e88-11e9-84b9-9a3602156ef2.jpg)


Freely adapted from the great [mapbox/rio-glui](https://github.com/mapbox/rio-glui)

### Install

You can install rio-viz using pip

Note: 3d visualization features are optional, you'll need to have `cython==0.28` installed before being able to install rio-viz

```bash 
$ pip install rio-viz
```
with 3d features
```
$ pip install -U pip cython==0.28
$ pip install rio-viz[mvt]
```

Built from source

```bash
$ git clone https://github.com/developmentseed/rio-viz.git
$ cd rio-viz
$ pip install -e .
```

### How To

```bash 
$ rio viz --help                                                                                                                  
Usage: rio viz [OPTIONS] SRC_PATHS...

  Rasterio Viz cli.

Options:
  --nodata NUMBER|nan        Set nodata masking values for input dataset.
  --minzoom INTEGER          Overwrite minzoom
  --maxzoom INTEGER          Overwrite maxzoom
  --style [satellite|basic]  Mapbox basemap
  --port INTEGER             Webserver port (default: 8080)
  --host TEXT                Webserver host url (default: 127.0.0.1)
  --mapbox-token TOKEN       Pass Mapbox token
  --no-check                 Ignore COG validation
  --simple                   Launch simple viewer
  --help                     Show this message and exit.

Note: 

You can provide multiple paths (e.g: bands stored as separate path) to rio-viz:

```bash
$ rio viz https://s3.eu-central-1.amazonaws.com/remotepixel-eu-central-1/sentinel-s2-l1c/tiles/18/T/XR/2019/4/21/0/B0{4,3,2}.tif
```

### Experimental 

rio-viz supports Mapbox VectorTiles encoding from a raster array. This feature was added to visualize sparse data stored as raster but will also work for dense array. This is highly experimental and might be slow to render in certain browser and/or for big rasters.

![](https://user-images.githubusercontent.com/10407788/56853984-4713b800-68fd-11e9-86a2-efbb041daeb0.gif)


### Template Factories
The HTML templates provided by rio-viz may be [injected](https://fastapi.tiangolo.com/tutorial/dependencies/) into an
external FastAPI app using the factory functions defined in `rio_viz.templates.template`.  This allows the raw HTML to
be reused in external applications without deploying rio-viz.  The parameters passed to each factory define which
endpoints are used by the template.  For example, if the path operation to create a tilejson is bound to the
`create_tilejson` function and the path operation to read metadata about a COG is bound to the `read_info` function, a
dependency can be created as follows:

```python
from rio_viz.templates.template import create_simple_template_factory

dependency = create_simple_template_factory(tilejson="create_tilejson", info="read_info")
```

## Contribution & Development

Issues and pull requests are more than welcome.

**dev install**

```bash
$ git clone https://github.com/developmentseed/rio-viz.git
$ cd rio-viz
$ pip install -e .[dev]
```

**Python3.7 only**

This repo is set to use `pre-commit` to run *my-py*, *flake8*, *pydocstring* and *black* ("uncompromising Python code formatter") when commiting new code.

```bash
$ pre-commit install
```

## Authors
Created by [Development Seed](<http://developmentseed.org>)

