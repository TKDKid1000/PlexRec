import os

from plexapi.library import MovieSection, ShowSection
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from plexapi.playlist import Playlist
from plexapi.exceptions import NotFound
from tqdm import tqdm

from .database import media_collection
from .similarity import embed, plot_similarity
from .suggest import suggest_media

plex = PlexServer(os.environ["PLEX_SERVER_URL"], os.environ["PLEX_TOKEN"])


def main():
    embeddings: list[float] = []
    media_names: list[str] = []
    media_states: list[bool] = []

    sections: [MovieSection, ShowSection] = (
        # plex.library.section("Movies"),
        # plex.library.section("TV Shows"),
    )

    section: MovieSection | ShowSection
    for section in sections:
        media: Show | Movie
        for media in tqdm(
            section.search()
        ):  # Search through all media (takes a while).
            id = media.guid
            db_result = media_collection.get(
                id, include=["metadatas", "documents", "embeddings"]
            )

            if len(db_result["ids"]) > 0:
                embeddings.append(db_result["embeddings"][0])
                media_names.append(db_result["metadatas"][0]["title"])
                media_states.append(
                    media.isPlayed
                )  # Switch to db_result["metadatas"][0]["watched"] once implemented.
            else:
                doc = f"""Title: {media.title}
                    Genres: {', '.join([genre.tag for genre in media.genres])}
                    Summary: {media.summary}"""
                embedding = embed([doc])[0]
                media_collection.add(
                    ids=id,
                    metadatas={
                        "title": media.title,
                        "watched": media.isPlayed,
                        "type": "show" if isinstance(media, Show) else "movie",
                    },
                    documents=doc,
                    embeddings=embedding,
                )

                embeddings.append(embedding)
                media_names.append(media.title)
                media_states.append(media.isPlayed)

    suggestions = suggest_media(plex)

    playlist_name = "Recommendations"
    playlist: Playlist

    try:
        playlist = plex.playlist(playlist_name)
        playlist.addItems(suggestions)
    except NotFound:
        playlist = plex.createPlaylist(playlist_name, items=suggestions)

    # plot_similarity(
    #     texts=media_names,
    #     embeddings=embeddings,
    #     colors=["green" if watched else "white" for watched in media_states],
    # )
