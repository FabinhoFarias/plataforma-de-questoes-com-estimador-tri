#!/usr/bin/env python3
"""Gera embeddings MiniLM e avalia regressores clássicos para A/B/C."""
from __future__ import annotations
import argparse, json
from pathlib import Path
import numpy as np
import pandas as pd
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.base import clone
from sklearn.neural_network import MLPRegressor
from sklearn.svm import SVR
from sklearn.linear_model import Ridge, ElasticNet, BayesianRidge, HuberRegressor, SGDRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import GroupShuffleSplit, GroupKFold, GridSearchCV, ParameterGrid
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score, make_scorer
from sklearn.decomposition import PCA
import joblib
from python.mac_embeddings.engine import DIMENSIONS, MODEL


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--csv',type=Path,default=Path('dados/processados/dataset_com_embeddings.csv'))
    ap.add_argument('--out',type=Path,default=Path('dados/modelos'))
    ap.add_argument('--embedding-dim',type=int,default=6,help='Dimensões PCA usadas no treino')
    ap.add_argument('--test-year',type=int,help='Reserva um ano inteiro para teste acadêmico')
    ap.add_argument('--validation-year',type=int,help='Reserva outro ano inteiro para validação acadêmica')
    ap.add_argument('--skip-grid-search',action='store_true',help='Usa os hiperparâmetros padrão, sem busca em CV')
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    df=pd.read_csv(args.csv)
    if 'embedding' not in df.columns:
        raise ValueError(f'{args.csv}: coluna embedding ausente; execute python -m python.tokenizar_dataset primeiro.')
    df=df.dropna(subset=['text','a','b','c','embedding']).copy()
    if 'text_source' in df.columns:
        api_ok=df.get('api_match',pd.Series('',index=df.index)).eq('confirmed')
        allowed=(df.text_source.eq('ENEM.DEV') & api_ok) | \
                (df.text_source.eq('QuestoesEnem') & df.metadata_match_status.eq('confirmed'))
        df=df[allowed].copy()
    df['text']=df.text.astype(str).str.strip(); df=df[df.text.ne('')]
    if 'matchQuality' in df.columns:
        df=df[df.matchQuality.eq('exact')].copy()
    if 'metadata_match_status' in df.columns:
        uncertain=~df.metadata_match_status.eq('confirmed') & (
            ~df.metadata_match_status.isin(['exact','fuzzy']) |
            (pd.to_numeric(df.get('metadata_match_score',0),errors='coerce')<.85))
        for column in ['assunto','competencia','habilidade','dificuldade']:
            if column in df.columns: df.loc[uncertain,column]=np.nan
    df=df.drop_duplicates(subset=['itemCode']).reset_index(drop=True)
    # Uma mesma questão pode reaparecer com outro código; preserve só um texto no teste.
    df['text_key']=df.text.str.lower().str.replace(r'\s+',' ',regex=True)
    df=df.drop_duplicates(subset=['text_key']).reset_index(drop=True)
    if df.itemCode.nunique()<10: raise ValueError('Treino exige ao menos 10 CO_ITEM distintos após filtros.')
    raw_X=np.asarray([json.loads(v) for v in df.embedding],dtype=np.float32)
    if raw_X.ndim != 2 or raw_X.shape[1] != DIMENSIONS or not np.isfinite(raw_X).all():
        raise ValueError(f'Embeddings inválidos; esperado vetor finito de {DIMENSIONS} dimensões por linha.')
    if not 2 <= args.embedding_dim <= min(DIMENSIONS, len(df)-1):
        raise ValueError(f'--embedding-dim deve estar entre 2 e {min(DIMENSIONS, len(df)-1)}.')
    Y=df[['a','b','c']].to_numpy(float)
    groups=df.text_key.to_numpy()
    if bool(args.test_year)!=bool(args.validation_year):
        raise ValueError('Informe --test-year e --validation-year juntos.')
    if args.test_year:
        if args.validation_year>=args.test_year:
            raise ValueError('--validation-year deve ser anterior a --test-year.')
        years=df['year'].astype(int).to_numpy()
        te=np.flatnonzero(years==args.test_year)
        val=np.flatnonzero(years==args.validation_year)
        tr=np.flatnonzero(years<args.validation_year)
        if min(map(len,(tr,val,te)))<10: raise ValueError('Cada divisão temporal precisa de ao menos 10 itens.')
    else:
        development,te=next(GroupShuffleSplit(n_splits=1,test_size=.1,random_state=42).split(raw_X,Y,groups))
        inner_train,inner_val=next(GroupShuffleSplit(n_splits=1,test_size=1/9,random_state=43).split(raw_X[development],Y[development],groups[development]))
        tr,val=development[inner_train],development[inner_val]
    pca=PCA(n_components=args.embedding_dim,random_state=42)
    pca.fit(raw_X[tr])
    reduced=pca.transform(raw_X).astype(np.float32)
    structural=df['text'].str.len().to_numpy(float).reshape(-1,1)
    structural=np.nan_to_num(structural)
    numeric_scaler=StandardScaler().fit(structural[tr])
    numeric= numeric_scaler.transform(structural).astype(np.float32)
    if 'skillCode' in df.columns:
        habilidade=df.get('habilidade',pd.Series(index=df.index,dtype='string')).astype('string')
        df['habilidade']=habilidade.where(habilidade.notna(),df['skillCode'].astype('string'))
    categorical_columns=['disciplineCode','assunto','competencia','habilidade','dificuldade']
    for column in categorical_columns:
        if column not in df.columns: df[column]='__missing__'
        df[column]=df[column].astype('string').fillna('__missing__').str.strip().replace('', '__missing__')
    encoder=OneHotEncoder(handle_unknown='ignore',sparse_output=False,dtype=np.float32)
    encoder.fit(df.iloc[tr][categorical_columns])
    categorical=encoder.transform(df[categorical_columns])
    X=np.hstack([reduced, numeric, categorical]).astype(np.float32)
    print(f'Base de treino: {len(df)} linhas | {df.itemCode.nunique()} itens | MiniLM: {DIMENSIONS} -> PCA: {args.embedding_dim}', flush=True)
    print(f'Metadados categóricos: {categorical_columns} -> {categorical.shape[1]} colunas one-hot; sem ano/posição', flush=True)
    print(f'Divisão: {len(tr)} treino / {len(val)} validação / {len(te)} teste | '
          + (f'anos {args.validation_year}/{args.test_year}' if args.test_year else 'grupos separados por texto'),flush=True)
    estimators={
      'ridge':Ridge(alpha=10.0),
      'elastic_net':MultiOutputRegressor(ElasticNet(alpha=0.01,l1_ratio=0.2,max_iter=3000,random_state=42)),
      'mlp':MLPRegressor(hidden_layer_sizes=(128,64),early_stopping=True,max_iter=300,random_state=42),
      'svr_rbf':MultiOutputRegressor(SVR(C=10.0,epsilon=0.05,kernel='rbf')),
      'bayesian_ridge':MultiOutputRegressor(BayesianRidge()),
      'huber':MultiOutputRegressor(HuberRegressor(epsilon=1.35,max_iter=300)),
      'sgd_huber':MultiOutputRegressor(SGDRegressor(loss='huber',alpha=1e-4,
                                                    max_iter=2000,tol=1e-3,random_state=42)),
    }
    grids={
      'ridge':{'alpha':[0.1,1.0,10.0,100.0]},
      'elastic_net':{'estimator__alpha':[0.001,0.01,0.1],
                     'estimator__l1_ratio':[0.2,0.7]},
      'mlp':{'hidden_layer_sizes':[(64,),(128,64)],'alpha':[0.001,0.1]},
      'svr_rbf':{'estimator__C':[0.5,2.0,10.0],
                 'estimator__epsilon':[0.05,0.2]},
      'bayesian_ridge':{'estimator__alpha_1':[1e-6,1e-4],
                        'estimator__lambda_1':[1e-6,1e-4]},
      'huber':{'estimator__epsilon':[1.35,1.75],
               'estimator__alpha':[0.0001,0.1]},
      'sgd_huber':{'estimator__alpha':[1e-5,1e-4,1e-3],
                   'estimator__penalty':['l2','elasticnet']},
    }
    search_rows=[]; chosen_params={}
    if not args.skip_grid_search:
        # A CV e a escolha de hiperparâmetros usam só o treino. A validação
        # escolhe o modelo por parâmetro; o teste permanece intocado até o fim.
        scales=np.maximum(Y[tr].std(axis=0),1e-8)
        def normalized_mae(y_true,y_pred):
            return -float(np.mean(np.abs(np.asarray(y_true)-np.asarray(y_pred))/scales))
        folds=GroupKFold(n_splits=3)
        for name,model in estimators.items():
            print(f'[{name}] grid search: {len(ParameterGrid(grids[name]))} combinações × 3 folds',flush=True)
            search=GridSearchCV(model,grids[name],scoring=make_scorer(normalized_mae),
                                cv=folds,refit=True,n_jobs=1,error_score='raise')
            search.fit(X[tr],Y[tr],groups=groups[tr])
            estimators[name]=search.best_estimator_
            chosen_params[name]=search.best_params_
            for params,score,rank in zip(search.cv_results_['params'],
                                         search.cv_results_['mean_test_score'],
                                         search.cv_results_['rank_test_score']):
                search_rows.append({'model':name,'params':json.dumps(params,sort_keys=True),
                                    'cv_normalized_MAE':-float(score),'rank':int(rank)})
            print(f'[{name}] melhores parâmetros: {search.best_params_}; MAE normalizado CV={-search.best_score_:.4f}',flush=True)
        pd.DataFrame(search_rows).to_csv(args.out/'grid_search_resultados.csv',index=False)
        (args.out/'melhores_hiperparametros.json').write_text(
            json.dumps(chosen_params,ensure_ascii=False,indent=2),encoding='utf-8')
    report=[]; validation=[]; fitted={}; predictions={}; val_predictions={}
    for name,model in estimators.items():
        print(f'[{name}] treinando...', flush=True)
        model.fit(X[tr],Y[tr]); fitted[name]=model; pred=model.predict(X[te]); predictions[name]=pred
        val_predictions[name]=model.predict(X[val])
        print(f'[{name}] concluído; calculando métricas', flush=True)
        for j,param in enumerate(['a','b','c']):
            report.append({'model':name,'parameter':param,'MAE':mean_absolute_error(Y[te,j],pred[:,j]),
                           'RMSE':mean_squared_error(Y[te,j],pred[:,j])**.5,'R2':r2_score(Y[te,j],pred[:,j])})
            validation.append({'model':name,'parameter':param,'MAE':mean_absolute_error(Y[val,j],val_predictions[name][:,j])})
    for label, indices in [('baseline_global', tr)]:
        baseline=np.tile(Y[indices].mean(axis=0),(len(te),1))
        predictions[label]=baseline
        val_predictions[label]=np.tile(Y[indices].mean(axis=0),(len(val),1))
        for j,param in enumerate(['a','b','c']):
            report.append({'model':label,'parameter':param,'MAE':mean_absolute_error(Y[te,j],baseline[:,j]),
                           'RMSE':mean_squared_error(Y[te,j],baseline[:,j])**.5,'R2':r2_score(Y[te,j],baseline[:,j])})
            validation.append({'model':label,'parameter':param,'MAE':mean_absolute_error(Y[val,j],val_predictions[label][:,j])})
    train_groups=df.iloc[tr].groupby('disciplineCode')[['a','b','c']].mean()
    baseline=[]; baseline_val=[]
    global_mean=Y[tr].mean(axis=0)
    for i in te:
        key=df.iloc[i]['disciplineCode']
        baseline.append(train_groups.loc[key].to_numpy() if key in train_groups.index else global_mean)
    for i in val:
        key=df.iloc[i]['disciplineCode']
        baseline_val.append(train_groups.loc[key].to_numpy() if key in train_groups.index else global_mean)
    baseline=np.asarray(baseline)
    val_predictions['baseline_area']=np.asarray(baseline_val)
    predictions['baseline_area']=baseline
    for j,param in enumerate(['a','b','c']):
        report.append({'model':'baseline_area','parameter':param,'MAE':mean_absolute_error(Y[te,j],baseline[:,j]),
                       'RMSE':mean_squared_error(Y[te,j],baseline[:,j])**.5,'R2':r2_score(Y[te,j],baseline[:,j])})
        validation.append({'model':'baseline_area','parameter':param,'MAE':mean_absolute_error(Y[val,j],val_predictions['baseline_area'][:,j])})
    metrics=pd.DataFrame(report); metrics.to_csv(args.out/'metricas.csv',index=False)
    val_metrics=pd.DataFrame(validation); val_metrics.to_csv(args.out/'metricas_validacao.csv',index=False)
    best_by_target={p:val_metrics.loc[val_metrics.parameter.eq(p)].sort_values('MAE').iloc[0]['model'] for p in ['a','b','c']}
    candidate_by_target={p:val_metrics.loc[val_metrics.parameter.eq(p)&~val_metrics.model.str.startswith('baseline')].sort_values('MAE').iloc[0]['model'] for p in ['a','b','c']}
    preds=np.column_stack([predictions[best_by_target[p]][:,j] for j,p in enumerate(['a','b','c'])]); test=df.iloc[te].copy()
    test[['pred_a','pred_b','pred_c']]=preds; test.to_csv(args.out/'previsoes_teste.csv',index=False)
    # Reajusta o produto final com todos os itens após escolher modelos na validação.
    final_pca=PCA(n_components=args.embedding_dim,random_state=42).fit(raw_X)
    final_scaler=StandardScaler().fit(structural)
    final_encoder=OneHotEncoder(handle_unknown='ignore',sparse_output=False,dtype=np.float32).fit(df[categorical_columns])
    final_X=np.hstack([final_pca.transform(raw_X),final_scaler.transform(structural),
                       final_encoder.transform(df[categorical_columns])]).astype(np.float32)
    final_models={name:clone(estimators[name]).fit(final_X,Y)
                  for name in set(best_by_target.values())|set(candidate_by_target.values()) if name in estimators}
    val_selected=np.column_stack([val_predictions[best_by_target[p]][:,j] for j,p in enumerate(['a','b','c'])])
    validation_error={p:float(np.quantile(abs(Y[val,j]-val_selected[:,j]),.9)) for j,p in enumerate(['a','b','c'])}
    area_mean=df.groupby('disciplineCode')[['a','b','c']].mean().to_dict('index')
    b_bands={str(area):[float(v) for v in np.quantile(group['b'],[1/3,2/3])]
             for area,group in df.groupby('disciplineCode')}
    joblib.dump({'models':final_models,'best_model_by_target':best_by_target,
                 'experimental_model_by_target':candidate_by_target,
                 'baseline_global':Y.mean(axis=0),'baseline_area':area_mean,
                 'validation_abs_error_p90':validation_error,'b_bands_by_area':b_bands,
                 'pca':final_pca,'numeric_scaler':final_scaler,'categorical_encoder':final_encoder,
                 'categorical_columns':categorical_columns,'numeric_columns':['text_length'],
                 'model_input_dimensions':final_X.shape[1],
                 'embedding_model':MODEL,'embedding_dimensions':DIMENSIONS,
                 'reduced_embedding_dimensions':args.embedding_dim,'targets':['a','b','c'],
                 'external_ready':True,'training_items':len(df)},args.out/'estimador_tri.joblib')
    print(metrics.to_string(index=False), flush=True); print(f'Escolha por validação: {best_by_target}', flush=True)

if __name__=='__main__': main()
