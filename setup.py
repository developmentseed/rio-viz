"""setup: rio-viz."""

from setuptools import find_packages, setup

with open("README.md") as f:
    long_description = f.read()

# Runtime requirements.
inst_reqs = [
    "braceexpand",
    "titiler.core>=0.3.2,<0.4",
    "rio-cogeo>=2.2",
    "uvicorn",
]

extra_reqs = {
    "mvt": ["rio-tiler-mvt==0.0.1.dev2"],
    "test": ["pytest", "pytest-cov", "pytest-asyncio", "requests"],
    "dev": ["pytest", "pytest-cov", "pytest-asyncio", "pre-commit"],
}

setup(
    name="rio-viz",
    version="0.7.0",
    python_requires=">=3.6",
    description=u"Visualize Cloud Optimized GeoTIFF in browser",
    long_description=long_description,
    long_description_content_type="text/markdown",
    classifiers=[
        "Intended Audience :: Information Technology",
        "Intended Audience :: Science/Research",
        "License :: OSI Approved :: BSD License",
        "Programming Language :: Python :: 3.6",
        "Programming Language :: Python :: 3.7",
        "Programming Language :: Python :: 3.8",
        "Topic :: Scientific/Engineering :: GIS",
    ],
    keywords="COG COGEO Rasterio GIS MVT",
    author=u"Vincent Sarago",
    author_email="vincent@developmentseed.org",
    url="https://github.com/developmentseed/rio-viz",
    packages=find_packages(exclude=["tests"]),
    include_package_data=True,
    zip_safe=False,
    license="MIT",
    install_requires=inst_reqs,
    extras_require=extra_reqs,
    entry_points="""
      [rasterio.rio_plugins]
      viz=rio_viz.scripts.cli:viz
      """,
)
