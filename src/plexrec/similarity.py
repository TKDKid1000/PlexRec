import os
from re import sub
from time import time

import matplotlib.pyplot as plt
import numpy as np
from numpy.linalg import norm
from plexapi.media import SubtitleStream
from plexapi.server import PlexServer
from plexapi.video import Movie
from sentence_transformers import SentenceTransformer
from sklearn.cluster import KMeans
from sklearn.manifold import TSNE

# oai = OpenAI(
#     api_key=os.environ["ANYSCALE_API_KEY"], base_url="https://api.endpoints.anyscale.com/v1"
# )


class FreeableSentenceTransformer:
    model_name: str
    model: SentenceTransformer

    def __init__(self, model_name: str) -> None:
        self.model_name = model_name
        self.model = None

    def load(self):
        if self.model is None:
            self.model = SentenceTransformer(self.model_name, trust_remote_code=True)

    def unload(self):
        self.model = None


embedder = FreeableSentenceTransformer("jinaai/jina-embeddings-v2-small-en")


def embed_subtitles(movie: Movie) -> list[SubtitleStream]:
    subtitles = movie.subtitleStreams()
    if len(subtitles) == 0:
        movie.downloadSubtitles(movie.searchSubtitles()[0])
    return subtitles
    # playlist = m3u8.load(streamUrl)
    # print(playlist.segments)


def embed(texts: list[str]) -> list[list[float]]:
    embedder.load()
    return embedder.model.encode(texts).tolist()


def cosine_similarity(a: list[float], b: list[float]):
    return np.dot(a, b) / (norm(a) * norm(b))


def plot_similarity(texts: list[str], embeddings: list[float], colors: list[str]):
    embeddings = np.array(embeddings)
    shrunk = TSNE(
        n_components=2, learning_rate="auto", init="pca", perplexity=3, random_state=42
    ).fit_transform(embeddings)

    x = [x for x, _ in shrunk]
    y = [y for _, y in shrunk]

    for idx, text in enumerate(texts):
        plt.text(x[idx], y[idx], text, fontdict={"size": 4})
    # plt.scatter(x, y, c=colors)

    kmeans = KMeans(n_clusters=20, random_state=42)
    kmeans.fit(list(zip(x, y)))

    # plt.scatter(x, y, c=kmeans.labels_)
    plt.scatter(x, y, c=colors)

    plt.show()


if __name__ == "__main__":
    plex = PlexServer(os.environ["PLEX_SERVER_URL"], os.environ["PLEX_TOKEN"])
    print(plex.url("/"))
    # print(plex.url("/library/metadata/192968/subtitles?forced=0&hearingImpaired=0&language=en", True))
    # print(embed_subtitles(plex.search("Taken")[0])[0].)
