# src/api/routes.py
"""
Регистрация API routes.
"""

from aiohttp import web

from src.api.handlers import events, plantings, user


def setup_routes(app: web.Application) -> None:
    """Регистрирует все API routes."""
    # Events
    app.router.add_get("/api/events", events.get_events)
    app.router.add_get("/api/events/{id}", events.get_event)
    app.router.add_post("/api/events", events.create_event)
    app.router.add_put("/api/events/{id}", events.update_event)
    app.router.add_delete("/api/events/{id}", events.delete_event)
    app.router.add_patch("/api/events/{id}/status", events.update_event_status)

    # Plantings
    app.router.add_get("/api/plantings", plantings.get_plantings)
    app.router.add_get("/api/plantings/{id}", plantings.get_planting)
    app.router.add_post("/api/plantings", plantings.create_planting)
    app.router.add_put("/api/plantings/{id}", plantings.update_planting)
    app.router.add_delete("/api/plantings/{id}", plantings.delete_planting)

    # User settings
    app.router.add_get("/api/user/region", user.get_region)
    app.router.add_put("/api/user/region", user.update_region)

    # Health check endpoint
    app.router.add_get("/api/health", health_check)


async def health_check(_request: web.Request) -> web.Response:
    """Health check endpoint."""
    return web.json_response({"status": "ok"})
