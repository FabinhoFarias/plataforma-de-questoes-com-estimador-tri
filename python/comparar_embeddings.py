#!/usr/bin/env python3
"""Compara os mesmos regressores com e sem embeddings no mesmo split."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'estimador_tri_matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', tempfile.gettempdir())
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from sklearn.decomposition import PCA
from sklearn.linear_model import ElasticNet, Ridge, BayesianRidge, HuberRegressor, SGDRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import GroupShuffleSplit
from sklearn.multioutput import MultiOutputRegressor
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.svm import SVR

from python.mac_embeddings.engine import DIMENSIONS


def prepare(path):
    df = pd.read_csv(path)
    required = {'text', 'a', 'b', 'c', 'embedding', 'itemCode'}
    if not required.issubset(df.columns):
        raise ValueError(f'Colunas ausentes: {sorted(required - set(df.columns))}')
    df = df.dropna(subset=list(required)).copy()
    if 'text_source' in df.columns:
        api_ok=df.get('api_match',pd.Series('',index=df.index)).eq('confirmed')
        allowed=(df.text_source.eq('ENEM.DEV') & api_ok) | \
                (df.text_source.eq('QuestoesEnem') & df.metadata_match_status.eq('confirmed'))
        df = df[allowed].copy()
    df['text'] = df.text.astype(str).str.strip()
    df = df[df.text.ne('')]
    if 'matchQuality' in df:
        df = df[df.matchQuality.eq('exact')].copy()
    if 'metadata_match_status' in df:
        reliable = df.metadata_match_status.eq('confirmed') | (
            df.metadata_match_status.isin(['exact', 'fuzzy']) & pd.to_numeric(
                df.get('metadata_match_score', 0), errors='coerce').ge(.85))
        for col in ['assunto', 'competencia', 'habilidade', 'dificuldade']:
            if col in df:
                df.loc[~reliable, col] = np.nan
    df = df.drop_duplicates('itemCode')
    df['text_key'] = df.text.str.lower().str.replace(r'\s+', ' ', regex=True)
    df = df.drop_duplicates('text_key').reset_index(drop=True)
    if 'skillCode' in df:
        df['habilidade'] = df.get('habilidade', pd.Series(index=df.index, dtype='string')).astype('string').fillna(
            df.skillCode.astype('string'))
    columns = ['disciplineCode', 'assunto', 'competencia', 'habilidade', 'dificuldade']
    for col in columns:
        if col not in df:
            df[col] = '__missing__'
        df[col] = df[col].astype('string').fillna('__missing__').str.strip().replace('', '__missing__')
    raw = np.asarray([json.loads(v) for v in df.embedding], dtype=np.float32)
    if raw.shape != (len(df), DIMENSIONS) or not np.isfinite(raw).all():
        raise ValueError('Embeddings inválidos ou com dimensão incompatível.')
    return df, raw, columns


def split(df, temporal):
    if temporal:
        validation_year, test_year = temporal
        if validation_year >= test_year:
            raise ValueError('Ano de validação deve ser anterior ao de teste.')
        year = pd.to_numeric(df.year, errors='coerce').to_numpy()
        tr = np.flatnonzero(year < validation_year)
        va = np.flatnonzero(year == validation_year)
        te = np.flatnonzero(year == test_year)
    else:
        groups = df.text_key.to_numpy()
        dev, te = next(GroupShuffleSplit(n_splits=1, test_size=.1, random_state=42).split(df, groups=groups))
        i_tr, i_va = next(GroupShuffleSplit(n_splits=1, test_size=1/9, random_state=43).split(
            df.iloc[dev], groups=groups[dev]))
        tr, va = dev[i_tr], dev[i_va]
    if min(len(tr), len(va), len(te)) < 10:
        raise ValueError('Cada divisão precisa ter pelo menos 10 itens.')
    return tr, va, te


def models():
    return {
        'ridge': Ridge(alpha=10.0),
        'elastic_net': MultiOutputRegressor(ElasticNet(alpha=.01, l1_ratio=.2, max_iter=3000, random_state=42)),
        'mlp': MLPRegressor(hidden_layer_sizes=(128, 64), early_stopping=True, max_iter=300, random_state=42),
        'svr_rbf': MultiOutputRegressor(SVR(C=10.0, epsilon=.05, kernel='rbf')),
        'bayesian_ridge': MultiOutputRegressor(BayesianRidge()),
        'huber': MultiOutputRegressor(HuberRegressor(epsilon=1.35, max_iter=300)),
        'sgd_huber': MultiOutputRegressor(SGDRegressor(loss='huber', alpha=1e-4,
                                                       max_iter=2000, tol=1e-3, random_state=42)),
    }


def feature_groups(encoder, columns, with_embeddings, embedding_dim):
    shift = embedding_dim if with_embeddings else 0
    groups = {}
    if with_embeddings:
        groups['embeddings_pca'] = np.arange(embedding_dim)
    groups['comprimento_texto'] = np.array([shift])
    start = shift + 1
    for name, categories in zip(columns, encoder.categories_):
        stop = start + len(categories)
        groups[name] = np.arange(start, stop)
        start = stop
    return groups


def permutation_importance(model, x, y, groups, repeats, seed):
    """Embaralha todas as colunas de cada grupo juntas; mede aumento do MAE."""
    rng = np.random.default_rng(seed)
    original = model.predict(x)
    base_mae = [mean_absolute_error(y[:, j], original[:, j]) for j in range(3)]
    rows = []
    for group_name, indices in groups.items():
        changes = []
        for _ in range(repeats):
            shuffled = x.copy()
            shuffled[:, indices] = x[rng.permutation(len(x))][:, indices]
            prediction = model.predict(shuffled)
            changes.append([mean_absolute_error(y[:, j], prediction[:, j]) - base_mae[j]
                            for j in range(3)])
        changes = np.asarray(changes)
        for j, target in enumerate(['a', 'b', 'c']):
            rows.append({'grupo': group_name, 'parametro': target,
                         'aumento_MAE_medio': float(changes[:, j].mean()),
                         'desvio_repeticoes': float(changes[:, j].std(ddof=1)) if repeats > 1 else 0.0,
                         'repeticoes': repeats, 'n_validacao': len(x)})
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv', type=Path, default=Path('dados/processados/dataset_com_embeddings.csv'))
    ap.add_argument('--out', type=Path, default=Path('dados/modelos/estudo_embeddings'))
    ap.add_argument('--embedding-dim', type=int, default=6)
    ap.add_argument('--reduced-embeddings', type=Path,
                    help='NPZ de vetores PCA ajustados somente no treino e alinhados por CO_ITEM')
    ap.add_argument('--validation-year', type=int)
    ap.add_argument('--test-year', type=int)
    ap.add_argument('--permutation-repeats', type=int, default=5,
                    help='Repetições por grupo na importância por permutação (validação)')
    ap.add_argument('--skip-importance', action='store_true')
    args = ap.parse_args()
    if bool(args.validation_year) != bool(args.test_year):
        ap.error('Informe os dois anos ou nenhum.')
    if args.permutation_repeats < 1:
        ap.error('--permutation-repeats deve ser positivo.')
    df, raw, columns = prepare(args.csv)
    tr, va, te = split(df, (args.validation_year, args.test_year) if args.test_year else None)
    if not 2 <= args.embedding_dim <= min(DIMENSIONS, len(tr)-1):
        ap.error('Dimensão PCA inválida para o tamanho do treino.')
    y = df[['a', 'b', 'c']].to_numpy(float)
    length = df.text.str.len().to_numpy(float).reshape(-1, 1)
    scaler = StandardScaler().fit(length[tr])
    encoder = OneHotEncoder(handle_unknown='ignore', sparse_output=False, dtype=np.float32).fit(df.iloc[tr][columns])
    base = np.hstack([scaler.transform(length), encoder.transform(df[columns])]).astype(np.float32)
    if args.reduced_embeddings:
        with np.load(args.reduced_embeddings) as saved:
            reduced=saved['embedding']
            item_codes=saved['item_codes'].astype(str)
            train_codes=saved['train_codes'].astype(str)
        if reduced.shape!=(len(df),args.embedding_dim) or not np.array_equal(item_codes,df.itemCode.astype(str).to_numpy()):
            raise ValueError('Vetores reduzidos não correspondem aos mesmos itens na mesma ordem.')
        if not np.array_equal(train_codes,df.iloc[tr].itemCode.astype(str).to_numpy()):
            raise ValueError('Vetores PCA ajustados em outra divisão de treino.')
    else:
        pca = PCA(n_components=args.embedding_dim, random_state=42).fit(raw[tr])
        reduced=pca.transform(raw)
    variants = {'sem_embeddings': base,
                'com_embeddings': np.hstack([reduced, base]).astype(np.float32)}
    rows = []
    importance_rows = []
    for variant, x in variants.items():
        print(f'{variant}: {x.shape[1]} atributos; {len(tr)} treino / {len(va)} validação / {len(te)} teste', flush=True)
        for name, model in models().items():
            print(f'  [{name}] treinando...', flush=True)
            model.fit(x[tr], y[tr])
            if not args.skip_importance:
                groups = feature_groups(encoder, columns, variant == 'com_embeddings', args.embedding_dim)
                importance_rows.extend({'variante': variant, 'modelo': name, **row}
                    for row in permutation_importance(model, x[va], y[va], groups,
                                                      args.permutation_repeats, 42))
            for subset, indices in [('validacao', va), ('teste', te)]:
                pred = model.predict(x[indices])
                for j, target in enumerate(['a', 'b', 'c']):
                    rows.append({'variante': variant, 'modelo': name, 'conjunto': subset,
                                 'parametro': target, 'n': len(indices),
                                 'MAE': mean_absolute_error(y[indices, j], pred[:, j]),
                                 'RMSE': mean_squared_error(y[indices, j], pred[:, j]) ** .5,
                                 'R2': r2_score(y[indices, j], pred[:, j])})
    results = pd.DataFrame(rows)
    train_area = df.iloc[tr].groupby('disciplineCode')[['a', 'b', 'c']].mean()
    global_mean = y[tr].mean(axis=0)
    baseline = np.asarray([train_area.loc[area].to_numpy() if area in train_area.index else global_mean
                           for area in df.iloc[te].disciplineCode])
    baseline_mae = {target: mean_absolute_error(y[te, j], baseline[:, j])
                    for j, target in enumerate(['a', 'b', 'c'])}
    args.out.mkdir(parents=True, exist_ok=True)
    results.to_csv(args.out / 'metricas.csv', index=False)
    test = results[results.conjunto.eq('teste')]
    comparison = test.pivot(index=['modelo', 'parametro'], columns='variante', values=['MAE', 'RMSE', 'R2'])
    comparison.columns = [f'{metric}_{variant}' for metric, variant in comparison.columns]
    comparison = comparison.reset_index()
    comparison['delta_MAE_com_menos_sem'] = comparison.MAE_com_embeddings - comparison.MAE_sem_embeddings
    comparison.to_csv(args.out / 'comparacao_teste.csv', index=False)
    if importance_rows:
        importance = pd.DataFrame(importance_rows)
        importance.to_csv(args.out / 'importancias_permutacao.csv', index=False)
        view = importance[importance.variante.eq('com_embeddings') & importance.parametro.eq('b')]
        chart = view.pivot(index='grupo', columns='modelo', values='aumento_MAE_medio')
        chart = chart.loc[chart.mean(axis=1).sort_values(ascending=True).index]
        fig, ax = plt.subplots(figsize=(10, 5))
        chart.plot.barh(ax=ax, width=.8)
        ax.axvline(0, color='black', linewidth=.7)
        ax.set_xlabel('Aumento do MAE de b ao embaralhar o grupo (validação)')
        ax.set_ylabel('Grupo de atributos')
        ax.set_title('Importância por permutação com embeddings')
        fig.tight_layout()
        images = args.out / 'imagens'
        images.mkdir(exist_ok=True)
        fig.savefig(images / 'importancia_grupos_b.png', dpi=160)
        plt.close(fig)
    lines = ['# Estudo de ablação dos embeddings', '',
             f'Mesmos {len(df)} itens exact únicos e mesmos índices de treino ({len(tr)}), '
             f'validação ({len(va)}) e teste ({len(te)}) nas duas variantes. '
             f'PCA de {args.embedding_dim} dimensões ajustada somente no treino.', '',
             'A variante sem embeddings usa comprimento do texto, área e metadados categóricos confiáveis. '
             'A outra acrescenta apenas os embeddings reduzidos. Ano e posição não são atributos.', '',
             'Delta MAE = MAE com embeddings − MAE sem embeddings; valor negativo indica melhora.', '',
             '| Modelo | Parâmetro | MAE sem | MAE com | Delta MAE | R² sem | R² com |',
             '|---|---|---:|---:|---:|---:|---:|']
    for row in comparison.itertuples():
        lines.append(f'| {row.modelo} | {row.parametro} | {row.MAE_sem_embeddings:.4f} | '
                     f'{row.MAE_com_embeddings:.4f} | {row.delta_MAE_com_menos_sem:+.4f} | '
                     f'{row.R2_sem_embeddings:.4f} | {row.R2_com_embeddings:.4f} |')
    lines += ['', '## Leitura', '',
              'Baseline por área no mesmo teste: ' + ', '.join(
                  f'MAE {target} = {baseline_mae[target]:.4f}' for target in ['a', 'b', 'c']) + '.',
              '',
              'Este teste mede ganho incremental no domínio ENEM para os modelos e hiperparâmetros atuais. '
              'Não demonstra calibração em questões externas. Valores no teste não devem ser usados para '
              'escolher hiperparâmetros; consulte também `metricas.csv` para a validação.', '']
    if importance_rows:
        lines += ['## Importância por permutação na validação', '',
                  'Aumento positivo do MAE ao embaralhar o grupo indica que o modelo o utilizou. '
                  'Aumento próximo de zero ou negativo não comprova ausência de informação: '
                  'atributos correlacionados podem se substituir. Cada repetição embaralha '
                  'as colunas do grupo juntas, preservando o vetor one-hot de cada linha.', '',
                  '![Importância dos grupos para b](imagens/importancia_grupos_b.png)', '',
                  '| Variante | Modelo | Grupo | ΔMAE a | ΔMAE b | ΔMAE c |',
                  '|---|---|---|---:|---:|---:|']
        pivot = importance.pivot(index=['variante', 'modelo', 'grupo'],
                                 columns='parametro', values='aumento_MAE_medio').reset_index()
        for row in pivot.itertuples():
            lines.append(f'| {row.variante} | {row.modelo} | {row.grupo} | '
                         f'{row.a:+.4f} | {row.b:+.4f} | {row.c:+.4f} |')
        lines.append('')
    (args.out / 'relatorio.md').write_text('\n'.join(lines), encoding='utf-8')
    print(comparison[['modelo', 'parametro', 'MAE_sem_embeddings', 'MAE_com_embeddings',
                      'delta_MAE_com_menos_sem']].to_string(index=False), flush=True)
    print(f'Relatório: {args.out / "relatorio.md"}', flush=True)


if __name__ == '__main__':
    main()
