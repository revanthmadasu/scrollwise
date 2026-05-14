import math

from generators.embedding_client import EMBEDDING_DIM, HashEmbeddingClient


def test_embedding_dimension():
    c = HashEmbeddingClient()
    e = c.embed("hello world")
    assert len(e) == EMBEDDING_DIM


def test_embedding_is_normalized():
    c = HashEmbeddingClient()
    e = c.embed("hello world")
    norm = math.sqrt(sum(x * x for x in e))
    assert abs(norm - 1.0) < 1e-6


def test_embedding_is_deterministic():
    c = HashEmbeddingClient()
    e1 = c.embed("foo bar")
    e2 = c.embed("foo bar")
    assert e1 == e2


def test_different_texts_differ():
    c = HashEmbeddingClient()
    e1 = c.embed("foo")
    e2 = c.embed("bar")
    assert e1 != e2
