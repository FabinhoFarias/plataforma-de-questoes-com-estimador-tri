#!/usr/bin/env python3
"""Avalia previsões em questões externas com respostas e/ou parâmetros calibrados."""
from __future__ import annotations
import argparse,json
from pathlib import Path
import pandas as pd
from sklearn.metrics import mean_absolute_error,mean_squared_error,r2_score

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--previsoes',type=Path,required=True,help='Saída JSON de python.prever_questoes')
    ap.add_argument('--respostas',type=Path,required=True,help='CSV longo: id,correta (0 ou 1)')
    ap.add_argument('--parametros',type=Path,help='CSV opcional com id,a,b,c calibrados externamente')
    ap.add_argument('--out',type=Path,default=Path('dados/modelos/avaliacao_externa.json'))
    ap.add_argument('--min-respostas',type=int,default=30)
    args=ap.parse_args()
    predictions=json.loads(args.previsoes.read_text(encoding='utf-8'))
    if isinstance(predictions,dict): predictions=[predictions]
    pred=pd.DataFrame([{'id':str(p['id']),'area':p['area'],
                        **{f'pred_{k}':p['parametros_estimados'][k] for k in ('a','b','c')},
                        'pred_b_textual':p['parametros_textuais_experimentais']['b']}
                       for p in predictions])
    if pred.empty or pred.id.duplicated().any(): raise ValueError('Previsões vazias ou com id duplicado.')
    answers=pd.read_csv(args.respostas,dtype={'id':'string'})
    if not {'id','correta'}<=set(answers.columns): raise ValueError('Respostas exigem colunas id,correta.')
    if not answers.correta.isin([0,1]).all(): raise ValueError('correta deve conter apenas 0 ou 1.')
    facility=answers.groupby('id').correta.agg(['mean','size']).reset_index().rename(columns={'mean':'proporcao_acertos','size':'n_respostas'})
    joined=pred.merge(facility,on='id',how='inner')
    joined=joined[joined.n_respostas>=args.min_respostas]
    if len(joined)<10: raise ValueError('Exigem-se ao menos 10 itens com o mínimo de respostas definido.')
    rho=float(joined['pred_b'].corr(joined['proporcao_acertos'],method='spearman'))
    rho_textual=float(joined['pred_b_textual'].corr(joined['proporcao_acertos'],method='spearman'))
    report={'n_itens':len(joined),'n_respostas':int(joined.n_respostas.sum()),
            'min_respostas_por_item':args.min_respostas,
            'spearman_b_versus_proporcao_acertos':rho if pd.notna(rho) else None,
            'spearman_b_textual_experimental_versus_proporcao_acertos':rho_textual if pd.notna(rho_textual) else None,
            'interpretacao':'Correlação negativa é esperada: maior b, menor taxa de acerto. Taxa de acerto não é parâmetro TRI calibrado.',
            'por_area':{str(area):{'n_itens':len(group),
                                  'spearman':(lambda x:float(x) if pd.notna(x) else None)(group.pred_b.corr(group.proporcao_acertos,method='spearman')) if len(group)>=3 else None}
                        for area,group in joined.groupby('area')}}
    if args.parametros:
        labels=pd.read_csv(args.parametros,dtype={'id':'string'})
        if not {'id','a','b','c'}<=set(labels.columns): raise ValueError('Parâmetros exigem colunas id,a,b,c.')
        if labels.id.duplicated().any(): raise ValueError('Parâmetros com id duplicado.')
        scored=joined.merge(labels[['id','a','b','c']],on='id',how='inner')
        if len(scored)<10: raise ValueError('Menos de 10 itens com respostas e parâmetros calibrados.')
        report['parametros_calibrados']={'n_itens':len(scored)}
        for key in ('a','b','c'):
            actual=scored[key].astype(float); estimated=scored[f'pred_{key}'].astype(float)
            report['parametros_calibrados'][key]={'MAE':float(mean_absolute_error(actual,estimated)),
                                                   'RMSE':float(mean_squared_error(actual,estimated)**.5),
                                                   'R2':float(r2_score(actual,estimated))}
        report['aviso_escala']='A comparação de a,b,c só é válida se a calibração externa estiver ligada à escala ENEM.'
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2,allow_nan=False))

if __name__=='__main__': main()
