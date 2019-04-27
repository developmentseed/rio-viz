# rio-viz

[![CircleCI](https://circleci.com/gh/developmentseed/rio-viz.svg?style=svg&circle-token=4e1d294fbe0e9f1ad874a013434b91d22111b35e)](https://circleci.com/gh/developmentseed/rio-viz)

Rasterio plugin to visualize Cloud Optimized GeoTIFF in browser.

![](https://user-images.githubusercontent.com/10407788/56367726-e4674180-61c3-11e9-86e4-c8825cc75677.png)


Freely adapted from the great [mapbox/rio-glui](github.com/mapbox/rio-glui)

### Install

```bash
$ git clone https://github.com/developmentseed/rio-viz.git
$ cd rio-viz

# python-vtzero will only compile with Cython < 0.29
$ pip install cython==0.28

$ pip install -e .
```

### How To

```bash 
$ rio viz --help
Usage: rio viz [OPTIONS] SRC_PATH

  Rasterio Viz cli.

Options:
  --style [satellite|basic]  Mapbox basemap
  --port INTEGER             Webserver port (default: 8080)
  --mapbox-token TOKEN       Pass Mapbox token
  --no-check                 Ignore COG validation
  --help                     Show this message and exit
```

Note: 

You can provide multiple paths (e.g: bands stored as separate path) to rio-viz:

```bash
$ rio viz https://s3.eu-central-1.amazonaws.com/remotepixel-eu-central-1/sentinel-s2-l1c/tiles/18/T/XR/2019/4/21/0/B0{4,3,2}.tif
```

### Experimental 

rio-viz support Mapbox VectorTiles encoding from raster array. This features was added to visualize spare data stored as raster but will also work for dense array. This is highly experimental and might be slow to render in certain browser and/or for big rasters.

![](https://user-images.githubusercontent.com/10407788/56853984-4713b800-68fd-11e9-86a2-efbb041daeb0.gif)


### Docker

You can use rio-viz directly from a docker container

```bash
$ docker-compose build viz
$ file=myfile.tif style=satellite docker-compose up
```