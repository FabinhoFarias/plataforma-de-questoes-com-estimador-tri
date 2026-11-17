#!/usr/bin/env python3
"""Compara quatro tamanhos PCA dos embeddings com os mesmos itens e divisão."""
from __future__ import annotations
import argparse, os, subprocess, sys, tempfile
from pathlib import Path

os.environ.setdefault('MPLCONFIGDIR', str(Path(tempfile.gettempdir())/'estimador_tri_matplotlib'))
os.environ.setdefault('XDG_CACHE_HOME', tempfile.gettempdir())
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.decomposition import PCA
from python.comparar_embeddings import prepare,split

DEFAULT_DIMS=(6,125,245,364)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv',type=Path,default=Path('dados/processados/dataset_com_embeddings.csv'))
    ap.add_argument('--out',type=Path,default=Path('dados/modelos/estudo_dimensoes'))
    ap.add_argument('--dimensions',type=int,nargs=4,default=DEFAULT_DIMS,
                    metavar='DIM',help='Quatro tamanhos PCA; padrão: 6 125 245 364')
    ap.add_argument('--validation-year',type=int)
    ap.add_argument('--test-year',type=int)
    args=ap.parse_args()
    dims=sorted(set(args.dimensions))
    if len(dims)!=4 or dims[0]<2 or dims[-1]>384:
        ap.error('Informe quatro dimensões distintas entre 2 e 384.')
    if bool(args.validation_year)!=bool(args.test_year):
        ap.error('Informe --validation-year e --test-year juntos.')
    args.out.mkdir(parents=True,exist_ok=True)
    df,raw,_=prepare(args.csv)
    train,validation_indices,test_indices=split(df,(args.validation_year,args.test_year) if args.test_year else None)
    if dims[-1]>min(raw.shape[1],len(train)):
        ap.error('A maior dimensão excede a quantidade de itens no treino.')
    train_set=set(train); validation_set=set(validation_indices)
    manifest=pd.DataFrame({'itemCode':df.itemCode.astype(str),'year':df.year,
                           'grupo':['treino' if i in train_set else 'validacao' if i in validation_set else 'teste'
                                    for i in range(len(df))]})
    manifest.to_csv(args.out/'itens_e_divisao.csv',index=False)
    item_codes=df.itemCode.astype(str).to_numpy(dtype=str)
    train_codes=item_codes[train]
    frames=[]
    for dim in dims:
        target=args.out/f'pca_{dim}'
        target.mkdir(parents=True,exist_ok=True)
        vector_path=target/'embeddings_pca.npz'
        pca=PCA(n_components=dim,random_state=42).fit(raw[train])
        np.savez_compressed(vector_path,embedding=pca.transform(raw).astype(np.float32),
                            item_codes=item_codes,train_codes=train_codes)
        cmd=[sys.executable,'-m','python.comparar_embeddings','--csv',str(args.csv),
             '--out',str(target),'--embedding-dim',str(dim),'--skip-importance',
             '--reduced-embeddings',str(vector_path)]
        if args.test_year:
            cmd.extend(['--validation-year',str(args.validation_year),'--test-year',str(args.test_year)])
        print(f'\nPCA {dim} dimensões',flush=True)
        subprocess.run(cmd,check=True)
        frame=pd.read_csv(target/'metricas.csv')
        frame['dimensoes_pca']=dim
        frames.append(frame)
    all_metrics=pd.concat(frames,ignore_index=True)
    all_metrics.to_csv(args.out/'metricas_todas_dimensoes.csv',index=False)
    test=all_metrics[(all_metrics.conjunto=='teste') & (all_metrics.variante=='com_embeddings')]
    validation=all_metrics[(all_metrics.conjunto=='validacao') & (all_metrics.variante=='com_embeddings')]
    best=validation.sort_values('MAE').drop_duplicates('parametro')
    best=best[['parametro','modelo','dimensoes_pca','MAE']].rename(columns={'MAE':'MAE_validacao'})
    chosen=best.merge(test,on=['parametro','modelo','dimensoes_pca'],how='left')
    chosen[['parametro','modelo','dimensoes_pca','MAE_validacao','MAE','RMSE','R2']].to_csv(
        args.out/'escolha_por_validacao.csv',index=False)
    fig,axes=plt.subplots(1,3,figsize=(15,4))
    for ax,parameter in zip(axes,['a','b','c']):
        part=test[test.parametro==parameter]
        for model,group in part.groupby('modelo'):
            ax.plot(group.dimensoes_pca,group.MAE,marker='o',label=model)
        ax.set_title(f'Parâmetro {parameter}')
        ax.set_xlabel('Dimensões PCA')
        ax.set_ylabel('MAE no teste')
        ax.set_xticks(dims)
    axes[-1].legend(loc='upper left',bbox_to_anchor=(1.02,1))
    fig.tight_layout()
    fig.savefig(args.out/'mae_por_dimensao.png',dpi=160,bbox_inches='tight')
    plt.close(fig)
    lines=['# Ablação da dimensão dos embeddings','',
           f'Dimensões testadas: {dims}. Mesmos {len(df)} itens, com '
           f'{len(train)} no treino, {len(validation_indices)} na validação e {len(test_indices)} no teste.',
           'Os CO_ITEM e a divisão estão em `itens_e_divisao.csv`; cada representação '
           'está salva em `pca_<dimensão>/embeddings_pca.npz`.',
           'A PCA é ajustada somente no treino. A escolha é feita pela validação; o teste é apenas avaliação final.','',
           '| Parâmetro | Modelo escolhido | Dimensões | MAE validação | MAE teste | R² teste |',
           '|---|---|---:|---:|---:|---:|']
    for row in chosen.itertuples():
        lines.append(f'| {row.parametro} | {row.modelo} | {row.dimensoes_pca} | '
                     f'{row.MAE_validacao:.4f} | {row.MAE:.4f} | {row.R2:.4f} |')
    lines += ['', '![MAE por dimensão](mae_por_dimensao.png)', '',
              'Consulte `metricas_todas_dimensoes.csv` para todos os modelos e a variante sem embeddings.','']
    (args.out/'relatorio.md').write_text('\n'.join(lines),encoding='utf-8')
    print(f'Relatório: {args.out/"relatorio.md"}',flush=True)

if __name__=='__main__': main()
