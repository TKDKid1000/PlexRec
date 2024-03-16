from dataclasses import asdict, dataclass

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


@dataclass
class RelevanceSuggestion:
    title: str
    relevance: float


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
    suggestion_titles = list(suggestion.title for suggestion in suggestions)

    playlist_name = config["playlist"]["name"]
    playlist: Playlist

    # Add items to the playlist, creating it if necessary.
    try:
        playlist = plex.playlist(playlist_name)
        # Add titles in groups of 5 because apparently Plex doesn't like large groups at once.
        GROUP_SIZE = 5
        for group_titles in [
            suggestion_titles[i : i + GROUP_SIZE]
            for i in range(0, len(suggestion_titles), GROUP_SIZE)
        ]:
            playlist.addItems(group_titles)

    except NotFound:
        playlist = plex.createPlaylist(playlist_name, items=suggestion_titles)

    if config["playlist"]["prune"]:
        # Prunes (removes) stale suggestions.
        for item in playlist.items():
            if item not in suggestion_titles:
                playlist.removeItem(item)


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
    added_penalty = np.ones(len(watched["ids"]))
    print(stars.shape)

    # Everything in this loop is to be used as weighting to calculate the average.
    for idx, metadata in enumerate(tqdm(watched["metadatas"])):
        try:
            media: Movie | Show = sections[metadata["type"]].get(metadata["title"])
        except NotFound:
            # Use search as a backup, just in case the exact title matching doesn't work
            # (ie. the movie was deleted, the title changed).
            results = sections[metadata["type"]].search(
                title=metadata["title"],
                maxresults=1,
            )
            print(results)

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
        suggestion_title = sections[suggestion_metadata["type"]].get(
            suggestion_metadata["title"]
        )
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
            relevance += (
                media.addedAt.timestamp() * config["weighting"]["added_penalty"]
            )

        suggestions.append(
            RelevanceSuggestion(title=suggestion_title, relevance=relevance)
        )

    suggestions = sorted(suggestions, key=lambda s: s.relevance)

    return suggestions[: n_results + 1]
