#!/usr/bin/env python3
"""Análise exploratória reproduzível dos parâmetros TRI e metadados."""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import unicodedata
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir()) / 'estimador_tri_matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', tempfile.gettempdir())
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import pearsonr, spearmanr

PARAMS = ['a', 'b', 'c']
AREAS = {'CH': 'Humanas', 'CN': 'Natureza', 'LC': 'Linguagens', 'MT': 'Matemática'}
COLORS = {'CH': '#5470c6', 'CN': '#39a88a', 'LC': '#d99045', 'MT': '#9b70b8'}


def load_data(path: Path):
    columns = ['year', 'disciplineCode', 'a', 'b', 'c', 'matchQuality',
               'metadata_match_status', 'metadata_match_score', 'assunto',
               'competencia', 'habilidade', 'dificuldade', 'text', 'itemCode',
               'position']
    available = pd.read_csv(path, nrows=0).columns
    required = {'year', 'disciplineCode', 'a', 'b', 'c', 'matchQuality', 'text', 'itemCode'}
    missing = required - set(available)
    if missing:
        raise ValueError(f'{path}: faltam colunas {sorted(missing)}')
    df = pd.read_csv(path, usecols=[c for c in columns if c in available])
    for col in PARAMS:
        df[col] = pd.to_numeric(df[col], errors='coerce')
    raw_count = len(df)
    exact_count = int(df.matchQuality.eq('exact').sum())
    df = df[df.matchQuality.eq('exact')].dropna(subset=PARAMS + ['text', 'itemCode']).copy()
    df['text'] = df.text.astype(str).str.strip()
    df = df[df.text.ne('')]
    df = df.drop_duplicates(subset=['itemCode'])
    df['text_key'] = df.text.str.lower().str.replace(r'\s+', ' ', regex=True)
    df = df.drop_duplicates(subset=['text_key']).copy()
    df['text_length'] = df.text.str.len()
    df['year'] = pd.to_numeric(df.year, errors='coerce')
    if 'metadata_match_status' in df:
        status = df.metadata_match_status.isin(['exact', 'fuzzy'])
        score = pd.to_numeric(df.get('metadata_match_score', 0), errors='coerce').ge(.85)
        df['metadata_reliable'] = df.metadata_match_status.eq('confirmed') | (status & score)
    else:
        df['metadata_reliable'] = False
    for col in ['assunto', 'competencia', 'habilidade', 'dificuldade']:
        if col not in df:
            df[col] = np.nan
        df.loc[~df.metadata_reliable, col] = np.nan
    return df, {'linhas_originais': raw_count, 'pareamento_exact': exact_count,
                'itens_unicos_analisados': len(df),
                'metadados_confiaveis': int(df.metadata_reliable.sum())}


def correlation(x, y):
    frame = pd.DataFrame({'x': x, 'y': y}).replace([np.inf, -np.inf], np.nan).dropna()
    if len(frame) < 3 or frame.x.nunique() < 2 or frame.y.nunique() < 2:
        return {'n': len(frame), 'pearson': None, 'p_pearson': None,
                'spearman': None, 'p_spearman': None}
    pr = pearsonr(frame.x, frame.y)
    sr = spearmanr(frame.x, frame.y)
    return {'n': len(frame), 'pearson': float(pr.statistic), 'p_pearson': float(pr.pvalue),
            'spearman': float(sr.statistic), 'p_spearman': float(sr.pvalue)}


def save(fig, out, name):
    fig.tight_layout()
    fig.savefig(out / name, dpi=160, bbox_inches='tight')
    plt.close(fig)


def plots(df, out):
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, col in zip(axes, PARAMS):
        low, high = df[col].quantile([.01, .99])
        ax.hist(df.loc[df[col].between(low, high), col], bins=35, color='#5470c6', alpha=.85)
        ax.set_title(f'{col} (percentis 1–99)')
        ax.set_xlabel(col)
        ax.set_ylabel('Itens')
    save(fig, out, '01_distribuicoes_abc.png')

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    ordered = [a for a in AREAS if a in set(df.disciplineCode)]
    for ax, col in zip(axes, PARAMS):
        ax.boxplot([df.loc[df.disciplineCode.eq(area), col].dropna() for area in ordered],
                   tick_labels=ordered, showfliers=False, patch_artist=True,
                   boxprops={'facecolor': '#a9bce8'})
        ax.set_title(f'{col} por área (outliers ocultos)')
        ax.set_ylabel(col)
    save(fig, out, '02_parametros_por_area.png')

    corr = df[PARAMS + ['text_length', 'position']].corr(method='spearman', numeric_only=True)
    fig, ax = plt.subplots(figsize=(6, 5))
    im = ax.imshow(corr, vmin=-1, vmax=1, cmap='coolwarm')
    ax.set_xticks(range(len(corr)), corr.columns)
    ax.set_yticks(range(len(corr)), corr.index)
    for i in range(len(corr)):
        for j in range(len(corr)):
            ax.text(j, i, f'{corr.iloc[i, j]:.2f}', ha='center', va='center')
    fig.colorbar(im, ax=ax, label='Spearman')
    ax.set_title('Correlações entre variáveis numéricas')
    save(fig, out, '03_correlacoes_spearman.png')

    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    counts = df.groupby(['year', 'disciplineCode']).size().unstack(fill_value=0)
    counts.plot.bar(stacked=True, ax=axes[0], color=[COLORS.get(c, '#888') for c in counts.columns])
    axes[0].set_title('Itens únicos por ano e área')
    axes[0].set_ylabel('Itens')
    metadata = pd.Series({'Confiáveis': int(df.metadata_reliable.sum()),
                          'Sem metadados confiáveis': int((~df.metadata_reliable).sum())})
    metadata.plot.bar(ax=axes[1], color=['#39a88a', '#d99045'], rot=0)
    axes[1].set_title('Cobertura dos metadados externos')
    axes[1].set_ylabel('Itens')
    save(fig, out, '04_cobertura.png')

    fig, ax = plt.subplots(figsize=(8, 5))
    rng = np.random.default_rng(42)
    for area, group in df.groupby('disciplineCode'):
        sample = group.iloc[rng.choice(len(group), min(len(group), 400), replace=False)]
        ax.scatter(sample.text_length, sample.b, s=12, alpha=.35,
                   label=AREAS.get(area, area), color=COLORS.get(area))
    ax.set_ylim(df.b.quantile(.01), df.b.quantile(.99))
    ax.set_xlabel('Comprimento do texto (caracteres)')
    ax.set_ylabel('Parâmetro b')
    ax.set_title('Texto × dificuldade TRI (b; eixo limitado aos percentis 1–99)')
    ax.legend()
    save(fig, out, '05_comprimento_texto_e_b.png')

    levels = ['Facil', 'Medio', 'Dificil']
    label = df.dificuldade.dropna().astype(str).map(lambda s: ''.join(
        c for c in unicodedata.normalize('NFKD', s) if not unicodedata.combining(c)).title())
    selected = df.loc[label.index].assign(dificuldade_norm=label)
    selected = selected[selected.dificuldade_norm.isin(levels)]
    if not selected.empty:
        fig, ax = plt.subplots(figsize=(7, 5))
        ax.boxplot([selected.loc[selected.dificuldade_norm.eq(level), 'b'] for level in levels],
                   tick_labels=levels, showfliers=False, patch_artist=True,
                   boxprops={'facecolor': '#a9bce8'})
        ax.set_title('Rótulo de dificuldade × parâmetro b')
        ax.set_ylabel('b (outliers ocultos)')
        save(fig, out, '06_rotulo_dificuldade_e_b.png')
    return selected


def fmt(value):
    return 'n/d' if value is None or pd.isna(value) else f'{value:.3f}'


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv', type=Path, default=Path('dados/processados/dataset_com_embeddings.csv'))
    ap.add_argument('--out', type=Path, default=Path('dados/analise_exploratoria'))
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)
    images = args.out / 'imagens'
    images.mkdir(exist_ok=True)
    df, counts = load_data(args.csv)
    if len(df) < 10:
        raise ValueError('São necessários ao menos 10 itens exact distintos.')
    selected = plots(df, images)
    pairs = [('a', 'b'), ('a', 'c'), ('b', 'c'),
             ('text_length', 'a'), ('text_length', 'b'), ('text_length', 'c')]
    correlations = {f'{x}_vs_{y}': correlation(df[x], df[y]) for x, y in pairs}
    by_area = {area: {'n': len(group),
                      'b_mediana': float(group.b.median()),
                      'comprimento_vs_b': correlation(group.text_length, group.b)}
               for area, group in df.groupby('disciplineCode')}
    summary = {'filtros': counts,
               'parametros': df[PARAMS].describe(percentiles=[.01, .25, .5, .75, .99]).to_dict(),
               'correlacoes': correlations, 'por_area': by_area,
               'rotulos_dificuldade': selected.dificuldade_norm.value_counts().to_dict(),
               'anos': {str(int(k)): int(v) for k, v in df.year.value_counts().sort_index().items()},
               'areas': {str(k): int(v) for k, v in df.disciplineCode.value_counts().items()}}
    (args.out / 'resumo.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    lines = ['# Análise exploratória do dataset TRI', '',
             f"Fonte: `{args.csv}`. Linhas originais: {counts['linhas_originais']}; "
             f"pareamentos exact: {counts['pareamento_exact']}; "
             f"itens únicos analisados: {counts['itens_unicos_analisados']}.", '',
             '## Distribuição dos parâmetros', '',
             '| Parâmetro | Mediana | Média | Desvio padrão | P1 | P99 | Mínimo | Máximo |',
             '|---|---:|---:|---:|---:|---:|---:|---:|']
    for p in PARAMS:
        s = df[p].describe(percentiles=[.01, .5, .99])
        lines.append(f"| {p} | {s['50%']:.3f} | {s['mean']:.3f} | {s['std']:.3f} | "
                     f"{s['1%']:.3f} | {s['99%']:.3f} | {s['min']:.3f} | {s['max']:.3f} |")
    lines += ['', '## Correlações exploratórias', '',
              '| Par | n | Pearson | p Pearson | Spearman | p Spearman |',
              '|---|---:|---:|---:|---:|---:|']
    for pair, v in correlations.items():
        lines.append(f"| {pair} | {v['n']} | {fmt(v['pearson'])} | {fmt(v['p_pearson'])} | "
                     f"{fmt(v['spearman'])} | {fmt(v['p_spearman'])} |")
    lines += ['', '## Por área', '', '| Área | n | Mediana b | Spearman texto × b |',
              '|---|---:|---:|---:|']
    for area, v in by_area.items():
        lines.append(f"| {AREAS.get(area, area)} ({area}) | {v['n']} | {v['b_mediana']:.3f} | "
                     f"{fmt(v['comprimento_vs_b']['spearman'])} |")
    overall_rho = correlations['text_length_vs_b']['spearman']
    area_rhos = [v['comprimento_vs_b']['spearman'] for v in by_area.values()]
    if overall_rho is not None and overall_rho < 0 and all(r is not None and r > 0 for r in area_rhos):
        lines += ['', 'A associação entre comprimento do texto e `b` muda de sinal ao separar por área. '
                  'Isso indica confusão pela composição das áreas; a correlação agregada não deve '
                  'ser interpretada isoladamente. As associações dentro de cada área ainda são fracas.']
    lines += ['', '## Qualidade e interpretação', '',
              f"- Metadados confiáveis em {counts['metadados_confiaveis']} de {len(df)} itens "
              f"({counts['metadados_confiaveis']/len(df):.1%}).",
              f"- Rótulos de dificuldade disponíveis: {selected.dificuldade_norm.value_counts().to_dict()}.",
              '- Pearson é sensível a valores extremos; consulte Spearman e os percentis antes de interpretar.',
              '- Os gráficos de distribuição e dispersão limitam a visualização aos percentis 1–99; '
              'as estatísticas e correlações usam todos os valores.',
              '- Valores p são descritivos: há múltiplas comparações e não foi feita correção para elas.',
              '- Correlação não demonstra previsão fora do ENEM nem calibração TRI em simulados externos.',
              '', '## Imagens', '']
    for path in sorted(images.glob('*.png')):
        lines.append(f'![{path.stem}](imagens/{path.name})')
        lines.append('')
    (args.out / 'relatorio.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f"{len(df)} itens analisados; relatório: {args.out / 'relatorio.md'}; imagens: {images}")


if __name__ == '__main__':
    main()
