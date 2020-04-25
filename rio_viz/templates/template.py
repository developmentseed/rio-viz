import os
from typing import Callable, Optional

from starlette.requests import Request
from starlette.templating import Jinja2Templates, _TemplateResponse

html_templates = Jinja2Templates(directory=os.path.dirname(__file__))


def create_template_factory(
    viewer: Optional[str] = "_viewer",
    simple_viewer: Optional[str] = "_simple_viewer",
    tilejson: Optional[str] = "_tilejson",
    metadata: Optional[str] = "_metadata",
    point: Optional[str] = "_point",
    info: Optional[str] = "_info",
) -> Callable:
    """
    Dynamically create a dependency which may be injected into a FastAPI app.  The input parameters are used to look up
    the specific URLs for each route.
    """
    def _template(request: Request) -> _TemplateResponse:
        """Create a template from a request"""
        template_params = {
            "context": {
                "request": request,
                "tilejson_endpoint": request.url_for(tilejson),
                # Mapbox parameters default to those defined in the CLI
                # These are overridden in the app itself
                "mapbox_token": "",
                "mapbox_style": "basic",
            },
            "media_type": "text/html",
        }

        if request.url == request.url_for(viewer):
            template_params["context"].update(
                {
                    "metadata_endpoint": request.url_for(metadata),
                    "point_endpoint": request.url_for(point),
                }
            )
            template_params["name"] = "index.html"
        elif request.url == request.url_for(simple_viewer):
            template_params["context"].update({"info_endpoint": request.url_for(info)})
            template_params["name"] = "simple.html"

        return html_templates.TemplateResponse(**template_params)

    return _template


template_factory = create_template_factory()
