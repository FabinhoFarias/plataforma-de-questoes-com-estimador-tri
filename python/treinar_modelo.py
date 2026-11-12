#!/usr/bin/env python3
"""Gera embeddings MiniLM e avalia regressores clássicos para A/B/C."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import GroupShuffleSplit
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
import joblib
from python.mac_embeddings.engine import DIMENSIONS, MODEL


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv',type=Path,default=Path('dados/processados/dataset_com_embeddings.csv'))
    ap.add_argument('--out',type=Path,default=Path('dados/modelos'))
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(args.csv)
    if 'embedding' not in df.columns:
        raise ValueError(f'{args.csv}: coluna embedding ausente; execute python -m python.tokenizar_dataset primeiro.')
    df=df.dropna(subset=['text','a','b','c','embedding']).copy()
    df['text']=df.text.astype(str).str.strip(); df=df[df.text.ne('')]
    if df.itemCode.nunique()<10: raise ValueError('Treino exige ao menos 10 CO_ITEM distintos após filtros.')
    X=np.asarray([json.loads(v) for v in df.embedding],dtype=np.float32)
    if X.ndim != 2 or X.shape[1] != DIMENSIONS or not np.isfinite(X).all():
        raise ValueError(f'Embeddings inválidos; esperado vetor finito de {DIMENSIONS} dimensões por linha.')
    Y=df[['a','b','c']].to_numpy(float)
    groups=df.itemCode.astype(str).to_numpy()
    tr,te=next(GroupShuffleSplit(n_splits=1,test_size=.2,random_state=42).split(X,Y,groups))
    estimators={
      'ridge':MultiOutputRegressor(__import__('sklearn.linear_model',fromlist=['Ridge']).Ridge(alpha=10.0)),
      'extra_trees':MultiOutputRegressor(ExtraTreesRegressor(n_estimators=300,min_samples_leaf=2,random_state=42,n_jobs=-1)),
      'random_forest':MultiOutputRegressor(RandomForestRegressor(n_estimators=300,min_samples_leaf=2,random_state=42,n_jobs=-1)),
    }
    report=[]; fitted={}
    for name,model in estimators.items():
        model.fit(X[tr],Y[tr]); fitted[name]=model; pred=model.predict(X[te])
        for j,param in enumerate(['a','b','c']):
            report.append({'model':name,'parameter':param,'MAE':mean_absolute_error(Y[te,j],pred[:,j]),
                           'RMSE':mean_squared_error(Y[te,j],pred[:,j])**.5,'R2':r2_score(Y[te,j],pred[:,j])})
    baseline=np.tile(Y[tr].mean(axis=0),(len(te),1))
    for j,param in enumerate(['a','b','c']):
        report.append({'model':'baseline_mean','parameter':param,'MAE':mean_absolute_error(Y[te,j],baseline[:,j]),
                       'RMSE':mean_squared_error(Y[te,j],baseline[:,j])**.5,'R2':r2_score(Y[te,j],baseline[:,j])})
    metrics=pd.DataFrame(report); metrics.to_csv(args.out/'metricas.csv',index=False)
    score=metrics[metrics.model!='baseline_mean'].groupby('model').MAE.mean(); best=score.idxmin()
    preds=fitted[best].predict(X[te]); test=df.iloc[te].copy()
    test[['pred_a','pred_b','pred_c']]=preds; test.to_csv(args.out/'previsoes_teste.csv',index=False)
    joblib.dump({'model':fitted[best],'embedding_model':MODEL,'embedding_dimensions':DIMENSIONS,'targets':['a','b','c']},args.out/'estimador_tri.joblib')
    print(metrics.to_string(index=False)); print(f'Melhor pela MAE média: {best}')

if __name__=='__main__': main()
