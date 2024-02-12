import os
from contextlib import asynccontextmanager

from fastapi import BackgroundTasks, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from plexapi.exceptions import NotFound
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from pydantic import BaseModel

from .config import config
from .suggest import save_generate_suggestions


class CreateSuggestion(BaseModel):
    n: int


class Suggestion(BaseModel):
    title: str
    link: str
    image: str
    summary: str
    # TODO: Add a "relevance" value from the history/memory once implemented.


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


plex = PlexServer(os.environ["PLEX_SERVER_URL"], os.environ["PLEX_TOKEN"])


def query_suggestions(n: int) -> list[Suggestion]:
    # TODO: Return suggestions from the history/memory once implemented.
    try:
        suggestions_playlist: Playlist = plex.playlist(config["playlist"]["name"])
        return [
            Suggestion(
                title=suggestion.title,
                link=suggestion.getWebURL(),
                image=plex.url(suggestion.thumb, includeToken=True),
                summary=suggestion.summary,
            )
            for suggestion in suggestions_playlist.items()
        ][:n]
    except NotFound:
        return []


@app.get("/", response_class=HTMLResponse)
def index(req: Request):
    return templates.TemplateResponse(
        request=req,
        name="index.jinja2",
        context={"suggestions": query_suggestions(10)},
    )


@app.get("/suggest")
def get_suggest(n: int = 5):
    return query_suggestions(n)


@app.post("/suggest")
def post_suggest(body: CreateSuggestion, background_tasks: BackgroundTasks):
    background_tasks.add_task(save_generate_suggestions, plex=plex, n_results=body.n)
    return {"message": "Running suggestions in the background."}


# TODO: Add API methods for removing suggestions, liking them, and disliking them.
# TODO: Add API method for viewing currently running suggestion jobs.
