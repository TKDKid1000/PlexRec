import os

from fastapi import BackgroundTasks, FastAPI
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
    # TODO: Add a "relevance" value from the history/memory once implemented.


app = FastAPI()

plex = PlexServer(os.environ["PLEX_SERVER_URL"], os.environ["PLEX_TOKEN"])


@app.get("/")
def index():
    return {}


@app.get("/suggest")
def get_suggest(n: int = 5):
    # TODO: Return suggestions from the history/memory once implemented.
    try:
        suggestions_playlist: Playlist = plex.playlist(config["playlist"]["name"])
        return [
            Suggestion(title=suggestion.title, link=suggestion.getWebURL())
            for suggestion in suggestions_playlist.items()
        ][:n]
    except NotFound:
        return []


@app.post("/suggest")
def post_suggest(body: CreateSuggestion, background_tasks: BackgroundTasks):
    background_tasks.add_task(save_generate_suggestions, plex=plex, n_results=body.n)
    return {"message": "Running suggestions in the background."}


# TODO: Add API methods for removing suggestions, liking them, and disliking them.
