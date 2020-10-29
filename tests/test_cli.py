"""tests rio_viz.server."""

import os
from unittest.mock import patch

import pytest
from click.testing import CliRunner

from rio_viz.scripts.cli import viz

cog_path = os.path.join(os.path.dirname(__file__), "fixtures", "cog.tif")
noncog_path = os.path.join(os.path.dirname(__file__), "fixtures", "noncog.tif")


@pytest.fixture(autouse=True)
def testing_env_var(monkeypatch):
    """Set testing env variable."""
    monkeypatch.delenv("MAPBOX_ACCESS_TOKEN", raising=False)


@patch("rio_viz.app.viz")
@patch("click.launch")
def test_viz_valid(launch, app):
    """Should work as expected."""
    app.return_value.get_template_url.return_value = "http://127.0.0.1:8080/index.html"
    app.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path])
    app.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.app.viz")
@patch("click.launch")
def test_viz_valid_style(launch, app):
    """Should work as expected."""
    app.return_value.get_template_url.return_value = "http://127.0.0.1:8080/index.html"
    app.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path, "--style", "satellite"])
    app.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.app.viz")
@patch("click.launch")
def test_viz_validEnvToken(launch, app, monkeypatch):
    """Should work as expected."""
    monkeypatch.setenv("MAPBOX_ACCESS_TOKEN", "pk.afakemapboxtoken")

    app.return_value.get_template_url.return_value = "http://127.0.0.1:8080/index.html"
    app.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path])
    app.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.app.viz")
@patch("click.launch")
def test_viz_validToken(launch, app):
    """Should work as expected."""
    app.return_value.get_template_url.return_value = "http://127.0.0.1:8080/index.html"
    app.return_value.start.return_value = True

    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [cog_path, "--mapbox-token", "pk.afakemapboxtoken"])
    app.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0


@patch("rio_viz.app.viz")
@patch("click.launch")
def test_viz_validInvalidToken(launch, app):
    """Should work as expected."""
    runner = CliRunner()
    result = runner.invoke(viz, [cog_path, "--mapbox-token", "sk.afakemapboxtoken"])
    app.assert_not_called()
    launch.assert_not_called()
    assert result.exception
    assert result.exit_code == 1


@patch("rio_viz.app.viz")
@patch("click.launch")
def test_viz_invalidCog(launch, app):
    """Should work as expected."""
    app.return_value.start.return_value = True
    launch.return_value = True

    runner = CliRunner()
    result = runner.invoke(viz, [noncog_path])
    assert app.call_args[0] is not noncog_path
    app.assert_called_once()
    assert not result.exception
    assert result.exit_code == 0
