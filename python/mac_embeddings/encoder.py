"""Inicializa engine.py local no melhor dispositivo disponível."""
from __future__ import annotations
import torch
from sentence_transformers import SentenceTransformer
from .engine import EmbeddingEngine, MODEL


def create_engine(batch_size: int = 64) -> EmbeddingEngine:
    if torch.cuda.is_available():
        device = "cuda"
    elif getattr(torch.backends, "mps", None) and torch.backends.mps.is_available():
        device = "mps"
    else:
        device = "cpu"
    model = SentenceTransformer(MODEL, device=device)
    engine = EmbeddingEngine(model=model, runtime=torch, device=device, batch_size=batch_size)
    engine.threads = torch.get_num_threads()
    return engine


def encode_texts(texts: list[str], batch_size: int = 64):
    engine = create_engine(batch_size)
    vectors=[]
    for start in range(0, len(texts), batch_size):
        result=engine.encode(texts[start:start+batch_size])
        vectors.extend(result['embeddings'])
        print(f"Embeddings: {min(start+batch_size,len(texts))}/{len(texts)}",flush=True)
    return vectors, engine
