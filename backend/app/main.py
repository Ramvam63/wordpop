"""FastAPI application: JSON API under /api, the PWA served from /."""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from . import __version__
from .config import get_settings
from .db import init_db
from .routers import admin, auth, billing, categories, me, push, quiz, starter, tasks, transfer, tts, words

# Show WordPop's own messages (scheduler runs, push errors) in the server logs.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s - %(message)s")


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(title="WordPop API", version=__version__, lifespan=lifespan)

for r in (auth, transfer, words, categories, me, quiz, push, starter, admin, tasks, tts, billing):
    app.include_router(r.router)


@app.get("/api/health", tags=["meta"])
def health():
    return {"status": "ok", "version": __version__}


frontend = get_settings().frontend_dir


class AppFiles(StaticFiles):
    """The PWA's files. "no-cache" makes browsers check for a newer version (a cheap 304
    when nothing changed) instead of guessing, so an update is never hidden behind an old
    copy in the browser's HTTP cache. The service worker still makes start-up instant."""

    async def get_response(self, path, scope):
        response = await super().get_response(path, scope)
        response.headers.setdefault("Cache-Control", "no-cache")
        return response

if frontend.exists():

    @app.get("/sw.js", include_in_schema=False)
    def service_worker():
        # Served from the root so it can control the whole app, and never cached.
        return FileResponse(
            frontend / "sw.js",
            media_type="application/javascript",
            headers={"Cache-Control": "no-cache"},
        )

    app.mount("/", AppFiles(directory=frontend, html=True), name="frontend")
