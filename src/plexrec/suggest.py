from dataclasses import asdict

import numpy as np
from plexapi.exceptions import NotFound
from plexapi.library import MovieSection, ShowSection
from plexapi.playlist import Playlist
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from tqdm import tqdm

from .config import config
from .database import media_collection
from .media import fetch_media
from .similarity import embed


def average_vectors(vectors: np.ndarray, weights: np.ndarray) -> np.ndarray:
    return np.average(vectors, axis=0, weights=weights)


def save_generate_suggestions(plex: PlexServer, n_results: int):
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
                metadatas=asdict(media),
                documents=doc,
                embeddings=embedding,
            )

    suggestions = suggest_media(plex, n_results=n_results)

    playlist_name = config["playlist"]["name"]
    playlist: Playlist

    # Add items to the playlist, creating it if necessary.
    try:
        playlist = plex.playlist(playlist_name)
        playlist.addItems(suggestions)
    except NotFound:
        playlist = plex.createPlaylist(playlist_name, items=suggestions)

    if config["playlist"]["prune"]:
        # Prunes (removes) stale suggestions.
        for item in playlist.items():
            if item not in suggestions:
                playlist.removeItem(item)


def suggest_media(
    plex: PlexServer,
    n_results: int = 10,
    types: list[str] = None,
):
    if types is None:
        types = ["show", "movie"]

    sections = {
        "movie": plex.library.section("Movies"),
        "show": plex.library.section("TV Shows"),
    }

    watched = media_collection.get(
        where={"$and": [{"watched": True}, {"type": {"$in": types}}]},
        include=["metadatas", "embeddings"],
    )

    stars = []
    if config["weighting"]["stars"]["include"]:
        for metadata in tqdm(watched["metadatas"]):
            media: Movie | Show = sections[metadata["type"]].get(metadata["title"])

            rating = media.userRating
            rating = (
                rating
                if rating is not None
                else config["weighting"]["stars"]["default"]
            )
            stars.append(rating)
    else:
        stars = [1.0] * len(watched["ids"])

    average = average_vectors(np.array(watched["embeddings"]), np.array(stars)).tolist()
    suggestion_metadatas = media_collection.query(
        query_embeddings=average,
        where={"$and": [{"watched": False}, {"type": {"$in": types}}]},
        n_results=n_results,
    )["metadatas"][0]

    print(average)

    suggestions = []

    for suggestion_metadata in suggestion_metadatas:
        suggestion = sections[suggestion_metadata["type"]].get(
            suggestion_metadata["title"]
        )
        suggestions.append(suggestion)

    return suggestions
