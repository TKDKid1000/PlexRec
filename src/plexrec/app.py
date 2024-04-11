import os
import re
from typing import Annotated

from fastapi import BackgroundTasks, FastAPI, Header, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from plexapi.exceptions import NotFound
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from pydantic import BaseModel
from requests_cache import CachedSession

from .config import config
from .database import media_collection
from .similarity import embed
from .suggest import save_generate_suggestions


class Suggestion(BaseModel):
    title: str
    link: str
    image: str
    summary: str
    # TODO: Add a "relevance" value from the history/memory once implemented.


app = FastAPI()

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


cached_session = CachedSession(
    "plex_api_cache",
    backend="sqlite",
    expire_after=config["cache"],
    urls_expire_after={re.compile(r"https://.*plex.direct:32400/playlists/.*"): 0},
)
plex = PlexServer(
    os.environ["PLEX_SERVER_URL"], os.environ["PLEX_TOKEN"], session=cached_session
)


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
        ][-n:]
    except NotFound:
        return []


@app.get("/", response_class=HTMLResponse)
def index(req: Request):
    return templates.TemplateResponse(
        request=req,
        name="index.jinja2",
        context={"suggestions": query_suggestions(10)},
    )


@app.get("/search")
def search(req: Request, q: str):
    (embedding,) = embed([q])
    results = media_collection.query(
        query_embeddings=embedding,
    )
    return results["metadatas"]


@app.get("/relations", response_class=HTMLResponse)
def relations(req: Request):
    return templates.TemplateResponse(request=req, name="relations.jinja2")


@app.get("/suggest")
def get_suggest(n: int = 5):
    return query_suggestions(n)


@app.post("/suggest")
def post_suggest(
    n: int,
    background_tasks: BackgroundTasks,
    req: Request,
    HX_Request: Annotated[str | None, Header(convert_underscores=True)] = None,
):
    background_tasks.add_task(save_generate_suggestions, plex=plex, n_results=n)
    if HX_Request:
        return templates.TemplateResponse(
            request=req, name="events/create_suggestion.jinja2"
        )
    return {"message": "Running suggestions in the background."}
    # TODO: Use SSE or something to follow up about whether or not requests complete. Else, other TODO and implement polling in client.


# TODO: Add API methods for removing suggestions, liking them, and disliking them.
@app.delete("/suggest")
def delete_suggest(id: int):
    return {"message": f"Removing {id} suggestions."}


@app.post("/suggest/like")
def like_suggest():
    return {"message": "Liking a suggestion."}


@app.post("/suggest/dislike")
def dislike_suggest():
    return {"message": "Disliking a suggestion."}


# TODO: Add API method for viewing currently running suggestion jobs.
@app.get("/jobs")
def get_jobs(
    req: Request,
    HX_Request: Annotated[str | None, Header(convert_underscores=True)] = None,
):
    jobs = []
    if HX_Request:
        return templates.TemplateResponse(
            request=req, name="events/jobs.jinja2", context={"jobs": jobs}
        )
    else:
        return {"jobs": jobs}
