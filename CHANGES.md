
## 0.7.0 (TBD)

* add `titiler.core` as dependencies to reduce code duplication.
* update code and templates to follow `titiler.core` specs.
<<<<<<< HEAD
* add `feature.{format}` post endpoint to get image from polygon shaped GeoJSON (https://github.com/developmentseed/rio-viz/pull/36)
=======
* refactor dependencies to remove bidx in info/metadata/stats (https://github.com/developmentseed/rio-viz/pull/37)
* refactor UI (https://github.com/developmentseed/rio-viz/pull/38)
* add simple **MosaicReader** (https://github.com/developmentseed/rio-viz/pull/32)

    ```bash
    $ rio viz "tests/fixtures/mosaic_cog{1,2}.tif" --reader rio_viz.io.MosaicReader
    ```
>>>>>>> 3ac5cc16635399e0fc1f0a845a58462c75cb01bd

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
