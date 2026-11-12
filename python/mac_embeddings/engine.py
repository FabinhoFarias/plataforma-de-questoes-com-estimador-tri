"""Adapter de inferência local; o modelo e o runtime são injetados na inicialização."""

import gc
import logging
import math
import threading
import time

MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIMENSIONS = 384
logger = logging.getLogger(__name__)


class BusyError(Exception):
    pass


class EmbeddingEngine:
    def __init__(self, model, runtime, device, batch_size):
        self.model = model
        self.runtime = runtime
        self.device = device
        self.batch_size = batch_size
        self.lock = threading.Lock()
        self.completed = 0
        self.last_seconds = 0.0
        self.last_count = 0
        self.threads = None
        self.tuning_results = []
        self.last_input_characters = 0
        self.last_longest_text = 0

    def metadata(self):
        return {
            "model": MODEL,
            "dimensions": DIMENSIONS,
            "normalized": False,
            "device": self.device,
            "gpu": self.device if self.device != "cpu" else "CPU",
            "batch_size": self.batch_size,
            "threads": self.threads,
            "calibration": self.tuning_results,
            "max_seq_length": self.model.max_seq_length,
            "busy": self.lock.locked(),
            "processed_texts": self.completed,
            "last_seconds": round(self.last_seconds, 3),
            "last_input_characters": self.last_input_characters,
            "last_longest_text": self.last_longest_text,
            "last_average_characters": round(self.last_input_characters / self.last_count, 1)
            if self.last_count else 0,
            "last_texts_per_second": round(self.last_count / self.last_seconds, 2)
            if self.last_seconds else 0,
        }

    def _encode(self, texts):
        # Apenas OOM reduz o lote; erros de modelo/runtime não são mascarados.
        while True:
            out_of_memory = False
            try:
                with self.runtime.inference_mode():
                    return self.model.encode(
                        texts,
                        batch_size=self.batch_size,
                        normalize_embeddings=False,
                        convert_to_numpy=True,
                        show_progress_bar=False,
                        precision="float32",
                    ).tolist()
            except RuntimeError as error:
                if "out of memory" not in str(error).lower() or self.batch_size == 1:
                    raise
                out_of_memory = True
            # Fora do except: libera também as referências mantidas pelo traceback.
            if out_of_memory:
                self.batch_size = max(1, self.batch_size // 2)
                gc.collect()
                if self.device == "mps":
                    self.runtime.mps.empty_cache()
                elif self.device == "cuda":
                    self.runtime.cuda.empty_cache()
                logger.warning("Memória insuficiente; repetindo com batch_size=%s", self.batch_size)

    def encode(self, texts):
        if not self.lock.acquire(blocking=False):
            raise BusyError("Processador ocupado; aguarde o lote atual.")
        started = time.perf_counter()
        try:
            vectors = self._encode(texts)
            if len(vectors) != len(texts) or any(
                len(v) != DIMENSIONS or not all(math.isfinite(x) for x in v)
                for v in vectors
            ):
                raise RuntimeError("Modelo retornou vetores inválidos.")
            self.last_seconds = time.perf_counter() - started
            self.last_count = len(texts)
            self.last_input_characters = sum(map(len, texts))
            self.last_longest_text = max(map(len, texts), default=0)
            self.completed += len(texts)
            logger.info("%s textos em %.2fs (%.2f textos/s), batch=%s threads=%s "
                        "caracteres=%s média=%.0f maior=%s",
                        len(texts), self.last_seconds,
                        len(texts) / self.last_seconds, self.batch_size, self.threads,
                        self.last_input_characters, self.last_input_characters / len(texts),
                        self.last_longest_text)
            return {"model": MODEL, "dimensions": DIMENSIONS,
                    "normalized": False, "embeddings": vectors}
        finally:
            self.lock.release()
