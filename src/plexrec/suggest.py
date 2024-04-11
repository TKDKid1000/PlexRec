from time import time
from typing import Literal

import numpy as np
from plexapi.exceptions import NotFound
from plexapi.library import MovieSection, ShowSection
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from pydantic import BaseModel, RootModel
from tqdm import tqdm

from .config import config
from .database import media_collection
from .media import fetch_media
from .similarity import embed


class RelevanceSuggestion(BaseModel):
    title: str
    type: Literal["show", "movie"]
    relevance: float


class GeneratedSuggestionGroup(BaseModel):
    time: float
    suggestions: list[RelevanceSuggestion]


GenerationSuggestions = RootModel[list[GeneratedSuggestionGroup]]


def average_vectors(vectors: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return np.average(vectors, axis=0, weights=weights)


def save_generate_suggestions(plex: PlexServer, n_results: int):
    generation_start = time()
    medias = fetch_media(plex)

    for media in tqdm(medias):
        db_result = media_collection.get(media.id)

        if len(db_result["ids"]) > 0:
            watched_metadatas = {"watched": media.watched}
            if db_result["metadatas"][0]["watched"] != media.watched:
                media_collection.update(media.id, metadatas=watched_metadatas)
        else:
            doc = f"""Title: {media.title}
                Genres: {media.genres}
                Summary: {media.summary}"""
            embedding = embed([doc])[0]
            media_collection.add(
                ids=media.id,
                metadatas=media.model_dump(),
                documents=doc,
                embeddings=embedding,
            )

    suggestions = suggest_media(plex, n_results=n_results)
    suggestion_media: list[Movie | Show] = []

    movie_section: MovieSection = plex.library.section("Movies")
    show_section: ShowSection = plex.library.section("TV Shows")

    for suggestion in suggestions:
        if suggestion.type == "movie":
            suggestion_media.append(movie_section.get(suggestion.title))
        else:
            suggestion_media.append(show_section.get(suggestion.title).episodes()[0])

    playlist_name = config["playlist"]["name"]

    # TODO: Use a conditional instead of an implicit try-except for this.
    try:
        ...
    except NotFound:
        plex.createPlaylist(playlist_name, items=suggestion_media[0])

    playlist: Playlist = plex.playlist(playlist_name)

    if config["playlist"]["prune"]:
        # Prunes (removes) stale suggestions.
        print(playlist.items())
        for item in playlist.items():
            playlist.removeItems(item)

    # Add titles in groups of 5 because apparently Plex doesn't like large groups at once.
    group_size = 5
    for groups in [
        suggestion_media[i : i + group_size]
        for i in range(0, len(suggestion_media), group_size)
    ]:
        playlist.addItems(groups)

    with open("suggestions.json", encoding="utf-8") as suggestions_file:
        suggestion_groups: GenerationSuggestions = (
            GenerationSuggestions.model_validate_json(suggestions_file.read())
        )
    suggestion_groups.root.append(
        GeneratedSuggestionGroup(suggestions=suggestions, time=generation_start)
    )
    with open("suggestions.json", "w", encoding="utf-8") as suggestions_file:
        suggestions_file.write(suggestion_groups.model_dump_json())


# TODO: Make this all async using asyncio.gather and asyncio.to_thread
def suggest_media(
    plex: PlexServer,
    n_results: int = 10,
    n_rerank: int = 100,
    types: list[str] = None,
) -> list[RelevanceSuggestion]:
    if types is None:
        types = ["show", "movie"]

    sections: dict[str, MovieSection | ShowSection] = {
        "movie": plex.library.section("Movies"),
        "show": plex.library.section("TV Shows"),
    }

    watched = media_collection.get(
        where={"$and": [{"watched": True}, {"type": {"$in": types}}]},
        include=["metadatas", "embeddings"],
    )

    stars = np.ones(len(watched["ids"]))

    # Everything in this loop is to be used as weighting to calculate the average.
    for idx, metadata in enumerate(
        tqdm(watched["metadatas"], desc="Average Embedding")
    ):
        try:
            media: Movie | Show = sections[metadata["type"]].get(metadata["title"])
        except NotFound:
            # Use search as a backup, just in case the exact title matching doesn't work
            # (ie. the movie was deleted, the title changed).
            results = sections[metadata["type"]].search(
                title=metadata["title"],
                maxresults=1,
            )

        if config["weighting"]["stars"]["include"]:
            rating = media.userRating
            rating = (
                rating
                if rating is not None
                else config["weighting"]["stars"]["default"]
            )
            stars[idx] = rating

    average = np.average(
        np.array(watched["embeddings"]),
        axis=0,
        weights=stars,
    )
    suggestion_results = media_collection.query(
        query_embeddings=average.tolist(),
        where={"$and": [{"watched": False}, {"type": {"$in": types}}]},
        include=["distances", "metadatas"],
        n_results=n_rerank,
    )
    suggestion_metadatas = suggestion_results["metadatas"][0]
    suggestion_distances = suggestion_results["distances"][0]

    suggestions = []

    for idx, suggestion_metadata in enumerate(suggestion_metadatas):
        try:
            media: Movie | Show = sections[suggestion_metadata["type"]].get(
                suggestion_metadata["title"]
            )
        except NotFound:
            # Use search as a backup, just in case the exact title matching doesn't work
            # (ie. the movie was deleted, the title changed).
            results = sections[suggestion_metadata["type"]].search(
                title=suggestion_metadata["title"],
                maxresults=1,
            )

        relevance = suggestion_distances[idx]
        if "added_penalty" in config["weighting"]:
            relevance -= (
                media.addedAt.timestamp() * config["weighting"]["added_penalty"]
            )

        if "critic" in config["weighting"]["ratings"]:
            relevance -= (
                media.rating or config["weighting"]["ratings"]["default"]
            ) * config["weighting"]["ratings"]["critic"]
        if "audience" in config["weighting"]["ratings"]:
            relevance -= (
                media.audienceRating or config["weighting"]["ratings"]["default"]
            ) * config["weighting"]["ratings"]["audience"]

        suggestions.append(
            RelevanceSuggestion(
                title=media.title, relevance=relevance, type=suggestion_metadata["type"]
            )
        )

    suggestions = sorted(suggestions, key=lambda s: s.relevance)

    return suggestions[:n_results]
