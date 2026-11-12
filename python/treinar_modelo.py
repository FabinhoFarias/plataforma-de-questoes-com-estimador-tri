#!/usr/bin/env python3
"""Gera embeddings MiniLM e avalia regressores clássicos para A/B/C."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.neural_network import MLPRegressor
from sklearn.svm import SVR
from sklearn.linear_model import Ridge, ElasticNet
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.decomposition import PCA
import joblib
from python.mac_embeddings.engine import DIMENSIONS, MODEL


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv',type=Path,default=Path('dados/processados/dataset_com_embeddings.csv'))
    ap.add_argument('--out',type=Path,default=Path('dados/modelos'))
    ap.add_argument('--embedding-dim',type=int,default=6,help='Dimensões PCA usadas no treino')
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(args.csv)
    if 'embedding' not in df.columns:
        raise ValueError(f'{args.csv}: coluna embedding ausente; execute python -m python.tokenizar_dataset primeiro.')
    df=df.dropna(subset=['text','a','b','c','embedding']).copy()
    df['text']=df.text.astype(str).str.strip(); df=df[df.text.ne('')]
    if 'matchQuality' in df.columns:
        df=df[df.matchQuality.eq('exact')].copy()
    df=df.drop_duplicates(subset=['itemCode']).reset_index(drop=True)
    if df.itemCode.nunique()<10: raise ValueError('Treino exige ao menos 10 CO_ITEM distintos após filtros.')
    raw_X=np.asarray([json.loads(v) for v in df.embedding],dtype=np.float32)
    if raw_X.ndim != 2 or raw_X.shape[1] != DIMENSIONS or not np.isfinite(raw_X).all():
        raise ValueError(f'Embeddings inválidos; esperado vetor finito de {DIMENSIONS} dimensões por linha.')
    if not 2 <= args.embedding_dim <= min(DIMENSIONS, len(df)-1):
        raise ValueError(f'--embedding-dim deve estar entre 2 e {min(DIMENSIONS, len(df)-1)}.')
    Y=df[['a','b','c']].to_numpy(float)
    groups=df.itemCode.astype(str).to_numpy()
    tr,te=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(raw_X,Y,groups))
    pca=PCA(n_components=args.embedding_dim,random_state=42)
    pca.fit(raw_X[tr])
    reduced=pca.transform(raw_X).astype(np.float32)
    structural=np.column_stack([
        df['year'].to_numpy(float), df['position'].to_numpy(float),
        df['text'].str.len().to_numpy(float),
        df['skillCode'].notna().to_numpy(float),
    ])
    structural=np.nan_to_num(structural)
    X=np.hstack([reduced, StandardScaler().fit_transform(structural)]).astype(np.float32)
    print(f'Base de treino: {len(df)} linhas | {df.itemCode.nunique()} itens | MiniLM: {DIMENSIONS} -> PCA: {args.embedding_dim}', flush=True)
    print(f'Divisão: {len(tr)} treino / {len(te)} teste | grupos separados por CO_ITEM', flush=True)
    estimators={
      'ridge':Ridge(alpha=10.0),
      'elastic_net':MultiOutputRegressor(ElasticNet(alpha=0.01,l1_ratio=0.2,max_iter=3000,random_state=42)),
      'mlp':MLPRegressor(hidden_layer_sizes=(128,64),early_stopping=True,max_iter=300,random_state=42),
      'svr_rbf':MultiOutputRegressor(SVR(C=10.0,epsilon=0.05,kernel='rbf')),
    }
    report=[]; fitted={}
    for name,model in estimators.items():
        print(f'[{name}] treinando...', flush=True)
        model.fit(X[tr],Y[tr]); fitted[name]=model; pred=model.predict(X[te])
        print(f'[{name}] concluído; calculando métricas', flush=True)
        for j,param in enumerate(['a','b','c']):
            report.append({'model':name,'parameter':param,'MAE':mean_absolute_error(Y[te,j],pred[:,j]),
                           'RMSE':mean_squared_error(Y[te,j],pred[:,j])**.5,'R2':r2_score(Y[te,j],pred[:,j])})
    for label, indices in [('baseline_global', tr)]:
        baseline=np.tile(Y[indices].mean(axis=0),(len(te),1))
        for j,param in enumerate(['a','b','c']):
            report.append({'model':label,'parameter':param,'MAE':mean_absolute_error(Y[te,j],baseline[:,j]),
                           'RMSE':mean_squared_error(Y[te,j],baseline[:,j])**.5,'R2':r2_score(Y[te,j],baseline[:,j])})
    train_groups=df.iloc[tr].groupby(['disciplineCode','year'])[['a','b','c']].mean()
    baseline=[]
    global_mean=Y[tr].mean(axis=0)
    for i in te:
        key=(df.iloc[i]['disciplineCode'],df.iloc[i]['year'])
        baseline.append(train_groups.loc[key].to_numpy() if key in train_groups.index else global_mean)
    baseline=np.asarray(baseline)
    for j,param in enumerate(['a','b','c']):
        report.append({'model':'baseline_area_year','parameter':param,'MAE':mean_absolute_error(Y[te,j],baseline[:,j]),
                       'RMSE':mean_squared_error(Y[te,j],baseline[:,j])**.5,'R2':r2_score(Y[te,j],baseline[:,j])})
    metrics=pd.DataFrame(report); metrics.to_csv(args.out/'metricas.csv',index=False)
    score=metrics[~metrics.model.str.startswith('baseline')].groupby('model').MAE.mean(); best=score.idxmin()
    preds=fitted[best].predict(X[te]); test=df.iloc[te].copy()
    test[['pred_a','pred_b','pred_c']]=preds; test.to_csv(args.out/'previsoes_teste.csv',index=False)
    joblib.dump({'model':fitted[best],'pca':pca,'model_input_dimensions':X.shape[1],
                 'embedding_model':MODEL,'embedding_dimensions':DIMENSIONS,
                 'reduced_embedding_dimensions':args.embedding_dim,'targets':['a','b','c']},args.out/'estimador_tri.joblib')
    print(metrics.to_string(index=False), flush=True); print(f'Melhor pela MAE média: {best}', flush=True)

if __name__=='__main__': main()
