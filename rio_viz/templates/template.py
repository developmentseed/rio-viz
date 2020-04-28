import os
from typing import Callable, Optional

from starlette.requests import Request
from starlette.templating import Jinja2Templates, _TemplateResponse

html_templates = Jinja2Templates(directory=os.path.dirname(__file__))


def create_simple_template_factory(
    tilejson: Optional[str] = "_tilejson", info: Optional[str] = "_info"
) -> Callable[[Request], _TemplateResponse]:
    """
    Create a dependency which may be injected into a FastAPI app.  The input parameters are used to look up the specific
    URLs for each route.
    """
    def _template(request: Request) -> _TemplateResponse:
        """Create a template of ``templates/simple.html`` from a request"""
        return html_templates.TemplateResponse(
            name="simple.html",
            context={
                "request": request,
                "tilejson_endpoint": request.url_for(tilejson),
                "info_endpoint": request.url_for(info),
                # Mapbox parameters default to those defined in the CLI
                # These are overridden in the app itself
                "mapbox_token": "",
                "mapbox_style": "basic",
            },
            media_type="text/html",
        )

    return _template


def create_index_template_factory(
    tilejson: Optional[str] = "_tilejson",
    metadata: Optional[str] = "_metadata",
    point: Optional[str] = "_point",
) -> Callable[[Request], _TemplateResponse]:
    """
    Create a dependency which may be injected into a FastAPI app.  The input parameters are used to look up the specific
    URLs for each route.
    """
    def _template(request: Request) -> _TemplateResponse:
        """Create a template of ``templates/index.html`` from a request"""
        return html_templates.TemplateResponse(
            name="index.html",
            context={
                "request": request,
                "tilejson_endpoint": request.url_for(tilejson),
                "metadata_endpoint": request.url_for(metadata),
                "point_endpoint": request.url_for(point),
                # Mapbox parameters default to those defined in the CLI
                # These are overridden in the app itself
                "mapbox_token": "",
                "mapbox_style": "basic",
            },
            media_type="text/html",
        )

    return _template


simple_template_factory = create_simple_template_factory()
index_template_factory = create_index_template_factory()
