#!/usr/bin/env python3
"""Estima parâmetros preliminares de questões externas a partir de JSON."""
from __future__ import annotations
import argparse,json,sys,contextlib
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from python.mac_embeddings.encoder import encode_texts
from python.mac_embeddings.engine import DIMENSIONS,MODEL

AREAS={'CH','CN','LC','MT'}

def normalize_item(item):
    area=str(item.get('area') or item.get('disciplineCode') or '').upper().strip()
    if area not in AREAS: raise ValueError(f'Área inválida: {area!r}; use CH, CN, LC ou MT.')
    stem=str(item.get('enunciado') or item.get('contexto') or item.get('text') or '').strip()
    if len(stem)<20: raise ValueError('Enunciado precisa ter pelo menos 20 caracteres.')
    alternatives=item.get('alternativas',item.get('alternatives',[]))
    if not isinstance(alternatives,list): raise ValueError('alternativas deve ser uma lista.')
    texts=[str(a.get('texto',a.get('text','')) if isinstance(a,dict) else a).strip() for a in alternatives]
    if texts and (len(texts)!=5 or any(not t for t in texts)):
        raise ValueError('Forneça cinco alternativas não vazias ou omita alternativas.')
    text=' '.join([stem,*texts]).strip()
    return area,text

def predict_items(items,artifact,encode=encode_texts):
    if not artifact.get('external_ready'): raise ValueError('Modelo antigo; execute python -m python.treinar_modelo novamente.')
    if artifact['embedding_model']!=MODEL or artifact['embedding_dimensions']!=DIMENSIONS:
        raise ValueError('Modelo de embeddings incompatível com o artefato.')
    normalized=[normalize_item(item) for item in items]
    with contextlib.redirect_stdout(sys.stderr):
        vectors,_=encode([text for _,text in normalized])
    raw=np.asarray(vectors,dtype=np.float32)
    if raw.shape!=(len(items),DIMENSIONS): raise ValueError('Embeddings com dimensão inesperada.')
    categorical=[]
    for item,(area,text) in zip(items,normalized):
        categorical.append({name:str(item.get(name) or ('__missing__' if name!='disciplineCode' else area))
                            for name in artifact['categorical_columns']})
    X=np.hstack([artifact['pca'].transform(raw),
                 artifact['numeric_scaler'].transform(np.array([[len(text)] for _,text in normalized])),
                 artifact['categorical_encoder'].transform(pd.DataFrame(categorical)[artifact['categorical_columns']])]).astype(np.float32)
    model_predictions={name:model.predict(X) for name,model in artifact['models'].items()}
    result=[]
    for i,(item,(area,_)) in enumerate(zip(items,normalized)):
        values={}
        for j,param in enumerate(('a','b','c')):
            name=artifact['best_model_by_target'][param]
            if name=='baseline_global': value=float(artifact['baseline_global'][j])
            elif name=='baseline_area': value=float(artifact['baseline_area'].get(area,dict(zip(('a','b','c'),artifact['baseline_global'])))[param])
            else: value=float(model_predictions[name][i,j])
            values[param]=value
        experimental={param:float(model_predictions[artifact['experimental_model_by_target'][param]][i,j])
                      for j,param in enumerate(('a','b','c'))}
        low,high=artifact['b_bands_by_area'][area]
        band='baixa' if values['b']<low else 'alta' if values['b']>high else 'media'
        experimental_band='baixa' if experimental['b']<low else 'alta' if experimental['b']>high else 'media'
        error=artifact['validation_abs_error_p90']['b']
        result.append({'id':item.get('id',i),'area':area,'parametros_estimados':values,
                       'parametros_textuais_experimentais':experimental,
                       'faixa_dificuldade_relativa':band,
                       'faixa_dificuldade_textual_experimental':experimental_band,
                       'intervalo_empirico_b_enem_90pct':[values['b']-error,values['b']+error],
                       'metodos':artifact['best_model_by_target'],
                       'modelos_textuais_experimentais':artifact['experimental_model_by_target'],
                       'status':'estimativa_preliminar_nao_calibrada',
                       'observacao':'Intervalo e faixas derivados de itens ENEM; cobertura não validada em simulados externos.'})
    return result

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,required=True,help='JSON com uma questão ou lista de questões')
    ap.add_argument('--model',type=Path,default=Path('dados/modelos/estimador_tri.joblib'))
    ap.add_argument('--out',type=Path,help='Arquivo JSON de saída; padrão: terminal')
    args=ap.parse_args()
    source=json.loads(args.input.read_text(encoding='utf-8'))
    items=source if isinstance(source,list) else [source]
    if not items or not all(isinstance(x,dict) for x in items): ap.error('Entrada deve conter uma questão ou lista de questões JSON.')
    output=predict_items(items,joblib.load(args.model))
    rendered=json.dumps(output if isinstance(source,list) else output[0],ensure_ascii=False,indent=2)
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True);args.out.write_text(rendered+'\n',encoding='utf-8')
        print(args.out)
    else: print(rendered)

if __name__=='__main__': main()
