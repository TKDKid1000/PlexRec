from chromadb import chromadb

# from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import os

chroma = chromadb.PersistentClient()

# oai_embedding_function = OpenAIEmbeddingFunction(
#     api_key=os.environ["TOGETHER_API_KEY"],
#     api_base="https://api.together.xyz/v1",
#     model_name="BAAI/bge-large-en-v1.5",
# )
media_collection = chroma.get_or_create_collection(
    name="media",  # embedding_function=oai_embedding_function
)
