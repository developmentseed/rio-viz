
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
