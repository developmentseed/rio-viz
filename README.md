# rio-viz

<p align="center">
  <img src="https://user-images.githubusercontent.com/10407788/60689165-78be7780-9e88-11e9-84b9-9a3602156ef2.jpg" style="max-width: 500px;"/>
  <p align="center">A Rasterio plugin to visualize Cloud Optimized GeoTIFF in browser.</p>
</p>

<p align="center">
  <a href="https://github.com/developmentseed/rio-viz/actions?query=workflow%3ACI" target="_blank">
      <img src="https://github.com/developmentseed/rio-viz/workflows/CI/badge.svg" alt="Test">
  </a>
  <a href="https://codecov.io/gh/developmentseed/rio-viz" target="_blank">
      <img src="https://codecov.io/gh/developmentseed/rio-viz/branch/master/graph/badge.svg" alt="Coverage">
  </a>
  <a href="https://pypi.org/project/rio-viz" target="_blank">
      <img src="https://img.shields.io/pypi/v/rio-viz?color=%2334D058&label=pypi%20package" alt="Package version">
  </a>
  <a href="https://github.com/developmentseed/rio-viz/blob/master/LICENSE" target="_blank">
      <img src="https://img.shields.io/github/license/developmentseed/rio-viz.svg" alt="Downloads">
  </a>
</p>


## Install

You can install rio-viz using pip

```bash
$ pip install rio-viz
```
with 3d feature

```bash
# 3d visualization features is optional, you'll need to have `cython==0.28` installed before being able to install `rio-viz["mvt"]`
$ pip install -U pip cython==0.28
$ pip install rio-viz["mvt"]
```

Built from source

```bash
$ git clone https://github.com/developmentseed/rio-viz.git
$ cd rio-viz
$ pip install -e .
```


## CLI

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
  --help                     Show this message and exit.

Note:
```

## 3D (Experimental)

rio-viz supports Mapbox VectorTiles encoding from a raster array. This feature was added to visualize sparse data stored as raster but will also work for dense array. This is highly experimental and might be slow to render in certain browser and/or for big rasters.

![](https://user-images.githubusercontent.com/10407788/56853984-4713b800-68fd-11e9-86a2-efbb041daeb0.gif)


## Contribution & Development

See [CONTRIBUTING.md](https://github.com/developmentseed/rio-viz/blob/master/CONTRIBUTING.md)

## Authors

Created by [Development Seed](<http://developmentseed.org>)

## Changes

See [CHANGES.md](https://github.com/developmentseed/rio-viz/blob/master/CHANGES.md).

## License

See [LICENSE.txt](https://github.com/developmentseed/rio-viz/blob/master/LICENSE)
