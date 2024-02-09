import numpy as np
from plexapi.library import MovieSection, ShowSection
from plexapi.server import PlexServer
from plexapi.video import Movie, Show

from .database import media_collection


def average_vectors(vectors: list[list[float]]):
    return np.average(np.array(vectors), axis=0).tolist()


def suggest_media(
    plex: PlexServer, n_results: int = 10, types: list[str] = ["show", "movie"]
):
    watched = media_collection.get(
        where={"$and": [{"watched": True}, {"type": {"$in": types}}]},
        include=["metadatas", "embeddings"],
    )
    watched_embeddings = watched["embeddings"]

    average = average_vectors(watched_embeddings)
    suggestion_metadatas = media_collection.query(
        query_embeddings=average,
        where={"$and": [{"watched": False}, {"type": {"$in": types}}]},
        n_results=n_results,
    )["metadatas"][0]

    suggestions = []

    sections: dict[str, MovieSection | ShowSection] = {
        "movie": plex.library.section("Movies"),
        "show": plex.library.section("TV Shows"),
    }

    for suggestion_metadata in suggestion_metadatas:
        suggestion = sections[suggestion_metadata["type"]].get(suggestion_metadata["title"])
        suggestions.append(suggestion)

    return suggestions
