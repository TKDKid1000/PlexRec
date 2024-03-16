from plexapi.library import MovieSection, ShowSection
from plexapi.server import PlexServer
from plexapi.video import Movie, Show
from tqdm import tqdm
from pydantic import BaseModel


class Media(BaseModel):
    id: str
    title: str
    summary: str
    watched: bool
    type: str
    genres: str


def fetch_media(plex: PlexServer):
    medias: list[Media] = []

    sections: tuple[MovieSection, ShowSection] = (
        plex.library.section("Movies"),
        plex.library.section("TV Shows"),
    )

    section: MovieSection | ShowSection
    for section in sections:
        media: Show | Movie
        for media in tqdm(section.search()):
            medias.append(
                Media(
                    id=media.guid,
                    title=media.title,
                    summary=media.summary,
                    watched=media.isPlayed,
                    type="show" if isinstance(media, Show) else "movie",
                    genres=", ".join([genre.tag for genre in media.genres]),
                ),
            )
    return medias
