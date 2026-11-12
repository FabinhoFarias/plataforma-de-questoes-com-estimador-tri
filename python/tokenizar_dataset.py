#!/usr/bin/env python3
"""Gera embeddings MiniLM locais para cada texto do dataset rotulado."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from python.mac_embeddings.encoder import encode_texts
from python.mac_embeddings.engine import DIMENSIONS, MODEL


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path, default=Path('dados/processados/dataset_tri.csv'))
    parser.add_argument('--out', type=Path, default=Path('dados/processados/dataset_com_embeddings.csv'))
    parser.add_argument('--batch-size', type=int, default=64)
    args = parser.parse_args()

    if args.batch_size < 1:
        parser.error('--batch-size precisa ser maior que zero')

    df = pd.read_csv(args.csv)
    required = {'text', 'itemCode', 'a', 'b', 'c'}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f'{args.csv}: colunas ausentes: {sorted(missing)}')

    df = df.dropna(subset=['text', 'itemCode', 'a', 'b', 'c']).copy()
    df['text'] = df['text'].astype(str).str.strip()
    df = df[df['text'].ne('')].reset_index(drop=True)
    if df.empty:
        raise ValueError('Dataset sem linhas com texto e parâmetros A/B/C; nada para vetorizar.')

    # Vetoriza cada texto único uma vez; provas diferentes podem repetir o mesmo item.
    unique_texts = df['text'].drop_duplicates().tolist()
    vectors, _engine = encode_texts(unique_texts, batch_size=args.batch_size)
    if len(vectors) != len(unique_texts) or any(len(vector) != DIMENSIONS for vector in vectors):
        raise RuntimeError(f'Esperava embeddings de {DIMENSIONS} dimensões para cada texto.')

    vector_by_text = {
        text: json.dumps(vector, separators=(',', ':'), allow_nan=False)
        for text, vector in zip(unique_texts, vectors)
    }
    df['embedding'] = df['text'].map(vector_by_text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(args.out, index=False, encoding='utf-8-sig')

    metadata_path = args.out.with_name(args.out.stem + '_metadata.json')
    metadata_path.write_text(json.dumps({
        'model': MODEL,
        'dimensions': DIMENSIONS,
        'normalized': False,
        'rows': len(df),
        'uniqueTexts': len(unique_texts),
        'sourceCsv': str(args.csv),
    }, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'{len(df)} linhas com embeddings de {DIMENSIONS} dimensões -> {args.out}')
    print(f'Metadados -> {metadata_path}')


if __name__ == '__main__':
    main()
