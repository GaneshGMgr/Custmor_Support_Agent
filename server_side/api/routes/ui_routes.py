# server_side\api\routes\ui_routes.py

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

router = APIRouter(tags=["UI"])


@router.get("/", response_class=HTMLResponse)
async def test_email_page(request: Request):
    """Render test email submission page."""
    return request.app.state.templates.get_template("test_email.html").render()


@router.get("/ui/inbox", response_class=HTMLResponse)
async def inbox_page(request: Request):
    """Render inbox dashboard page."""
    return request.app.state.templates.get_template("inbox.html").render()


@router.get("/ui/test", response_class=HTMLResponse)
async def test_email_page_alt(request: Request):
    """Alias for test email page."""
    return request.app.state.templates.get_template("test_email.html").render()


@router.get("/ui/followups", response_class=HTMLResponse)
async def followups_dashboard_page(request: Request):
    """Render follow-up monitoring dashboard page."""
    return request.app.state.templates.get_template("followups_dashboard.html").render()
