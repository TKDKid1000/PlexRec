import os

import matplotlib.pyplot as plt
import numpy as np
from numpy.linalg import norm
from openai import OpenAI
from openai.types import CreateEmbeddingResponse
from sklearn.manifold import TSNE
from sklearn.cluster import KMeans
from sentence_transformers import SentenceTransformer
from time import time

# oai = OpenAI(
#     api_key=os.environ["ANYSCALE_API_KEY"], base_url="https://api.endpoints.anyscale.com/v1"
# )

embedder = SentenceTransformer(
    "jinaai/jina-embeddings-v2-small-en", trust_remote_code=True
)


def embed(texts: list[str]):
    # embedding: CreateEmbeddingResponse = oai.embeddings.create(
    #     model="BAAI/bge-large-en-v1.5",
    #     input=texts,
    # )
    # return [e.embedding for e in embedding.data]
    return embedder.encode(texts).tolist()


def cosine_similarity(a: list[float], b: list[float]):
    return np.dot(a, b) / (norm(a) * norm(b))


def plot_similarity(texts: list[str], embeddings: list[float], colors: list[str]):
    embeddings = np.array(embeddings)
    shrunk = TSNE(
        n_components=2, learning_rate="auto", init="pca", perplexity=3
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
