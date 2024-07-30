import json
from time import time
from typing import Literal, Optional

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
    weighted_average: Optional[list[float]] = None


GenerationSuggestions = RootModel[list[GeneratedSuggestionGroup]]


def average_vectors(vectors: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return np.average(vectors, axis=0, weights=weights)


def save_generate_suggestions(plex: PlexServer, n_results: int):
    # Initialize generation start and media list.
    generation_start = time()
    medias = fetch_media(plex)

    # Iterate media list.
    for media in tqdm(medias):
        # Get media from vector db.
        db_result = media_collection.get(media.id)

        if len(db_result["ids"]) > 0:
            # If it exists, update the watched state to whatever it currently is.
            watched_metadatas = {"watched": media.watched}
            if db_result["metadatas"][0]["watched"] != media.watched:
                media_collection.update(media.id, metadatas=watched_metadatas)
        else:
            # If it doesn't exist, embed and add it in.
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

    suggestions, average = suggest_media(
        plex, n_results=n_results
    )  # Get suggestion objects.
    suggestion_media: list[Movie | Show] = []  # Initialize Plex API suggestion list.

    movie_section: MovieSection = plex.library.section("Movies")
    show_section: ShowSection = plex.library.section("TV Shows")

    # Iterate suggestions and add them to API media list.
    for suggestion in suggestions:
        if suggestion.type == "movie":
            suggestion_media.append(movie_section.get(suggestion.title))
        else:
            # If it's a show, add the first episode, as Plex requires adding episodes, not entire shows.
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

    # Read the suggestion groups from the suggestions.json file.
    with open("suggestions.json", encoding="utf-8") as suggestions_file:
        suggestion_groups: GenerationSuggestions = (
            GenerationSuggestions.model_validate_json(suggestions_file.read())
        )

    # Add the suggestion to the list.
    suggestion_groups.root.append(
        GeneratedSuggestionGroup(
            suggestions=suggestions, time=generation_start, weighted_average=average
        )
    )

    # Write back the updated suggestions.
    with open("suggestions.json", "w", encoding="utf-8") as suggestions_file:
        suggestions_file.write(suggestion_groups.model_dump_json())


# TODO: Make this all async using asyncio.gather and asyncio.to_thread
def suggest_media(
    plex: PlexServer,
    n_results: int = 100,
    n_rerank: int = 500,
    types: list[str] | None = None,
) -> list[RelevanceSuggestion]:
    if types is None:
        types = ["show", "movie"]

    sections: dict[str, MovieSection | ShowSection] = {
        "movie": plex.library.section("Movies"),
        "show": plex.library.section("TV Shows"),
    }

    # Get all watched items from the vector database.
    watched = media_collection.get(
        where={"$and": [{"watched": True}, {"type": {"$in": types}}]},
        include=["metadatas", "embeddings"],
    )

    # Initialize array of stars.
    stars = np.ones(len(watched["ids"]))

    # Everything in this loop is to be used as weighting to calculate the average.
    for idx, metadata in enumerate(
        tqdm(watched["metadatas"], desc="Average Embedding")
    ):
        media: Movie | Show | None = None
        try:
            # Get the Plex API media from the database item's title.
            media = sections[metadata["type"]].get(metadata["title"])
        except NotFound:
            # Use search as a backup, just in case the exact title matching doesn't work
            # (ie. the movie was deleted, the title changed).
            results = sections[metadata["type"]].search(
                title=metadata["title"],
                maxresults=1,
            )

        # If enabled, apply star ratings.
        if config["weighting"]["stars"]["include"] and media is not None:
            rating = media.userRating
            rating = (
                rating
                if rating is not None
                else config["weighting"]["stars"]["default"]
            )  # Set Plex API value or default if there is not one.
            stars[idx] = rating

    # Find average of embeddings, weighted by stars, which is the most preferable vector.
    average = np.average(
        np.array(watched["embeddings"]),
        axis=0,
        weights=stars,
    )

    # Load ids of recommendations that were disliked in the web app.
    with open("disliked.json", encoding="utf-8") as disliked_file:
        disliked_ids: list[str] = json.load(disliked_file)

    # Get embeddings of those disliked recommendations.
    disliked_embeddings = media_collection.get(
        ids=disliked_ids, include=["embeddings"]
    )["embeddings"]

    # Subtract every dislike from the average to push away from it.
    for embedding in disliked_embeddings:
        # average = np.:

        average = np.subtract(average, embedding)

    # Get all unwatched and not disliked suggestion results of a type (movie/show) from a vector query.
    suggestion_results = media_collection.query(
        query_embeddings=average.reshape(
            1, -1
        ),  # Add a dimension, as chroma wanted a matrix.
        where={
            "$and": [
                {"watched": False},
                {"type": {"$in": types}},
                {"id": {"$nin": disliked_ids}},
            ]
        },
        include=["distances", "metadatas"],
        n_results=n_rerank,
    )
    suggestion_metadatas = suggestion_results["metadatas"][0]
    suggestion_distances = suggestion_results["distances"][0]

    suggestions = []

    # Iterate all queried suggestions.
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

        relevance = 1 - (
            suggestion_distances[idx] / 100
        )  # Relevance starts as the similarity to the average from 0-1.

        # Add in the added penalty; negative favors old, positive favors new.
        if "added" in config["weighting"]:

            date_added = media.addedAt.timestamp()
            # * config["weighting"]["added_penalty"]
            # Value from 0-1: date_added/unix_ts

            relevance += date_added / time() * config["weighting"]["added"]

        # Factor in critic rating, going from 0-1.
        if "critic" in config["weighting"]["ratings"]:
            relevance -= (
                media.rating or config["weighting"]["ratings"]["default"]
            ) * config["weighting"]["ratings"]["critic"]

        # Factor in audience rating, going from 0-1.
        if "audience" in config["weighting"]["ratings"]:
            relevance -= (
                media.audienceRating or config["weighting"]["ratings"]["default"]
            ) * config["weighting"]["ratings"]["audience"]

        suggestions.append(
            RelevanceSuggestion(
                title=media.title, relevance=relevance, type=suggestion_metadata["type"]
            )
        )

    suggestions = sorted(suggestions, key=lambda s: s.relevance, reverse=True)

    return suggestions[:n_results], average
