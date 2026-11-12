#!/usr/bin/env python3
"""Junta texto de provas em JSON aos parâmetros A/B/C oficiais do INEP.

Entrada: dados/processados/textos/questoes_texto_inep.json e tabelas ITENS_PROVA
extraídas para dados/extraidos/<ano>/itens/. A junção exige ano, cor, dia,
posição/código, área e gabarito quando disponível. Dúvidas vão para revisão.
"""
from __future__ import annotations
import argparse,csv,json,re
from pathlib import Path

AREA_LABELS={'CH':'ciencias-humanas','CN':'ciencias-natureza','LC':'linguagens','MT':'matematica'}
COLOR_ALIASES={'AMARELA':'AMARELO','BRANCA':'BRANCO'}
PARAMS={'a':'NU_PARAM_A','b':'NU_PARAM_B','c':'NU_PARAM_C'}


def read_item_rows(root:Path, years:set[int]):
    rows=[]
    for path in root.glob('* /itens/*.csv'):
        pass
    for path in root.glob('*/itens/*.csv'):
        m=re.search(r'(19\d{2}|20\d{2})',path.parts[-3])
        if not m: continue
        year=int(m.group(1))
        if year not in years: continue
        with path.open(encoding='latin1',newline='') as f:
            reader=csv.DictReader(f,delimiter=';')
            fields=reader.fieldnames or []
            required={'CO_POSICAO','SG_AREA','CO_ITEM','TX_GABARITO','TX_COR','CO_PROVA',*PARAMS.values()}
            missing=required-set(fields)
            if missing: raise ValueError(f'{path}: faltam {sorted(missing)}')
            for r in reader:
                color=COLOR_ALIASES.get(r['TX_COR'].strip().upper(),r['TX_COR'].strip().upper())
                pos=int(r['CO_POSICAO'])
                # edição 2009 tem posições globais em 4 faixas; outras edições usam posição por área/prova.
                if year==2009:
                    day=1 if pos<=135 else 2
                    local_index=pos-45 if pos<=90 else pos-90 if pos<=135 else pos-135
                else:
                    # Mapeamento conservador: áreas CH/CN são dia 1; LC/MT dia 2 no formato pós-2009.
                    day=1 if r['SG_AREA'] in ('CH','CN') else 2
                    local_index=pos
                rows.append({'year':year,'examColor':color,'day':day,'examCode':r['CO_PROVA'].strip(),
                             'disciplineCode':r['SG_AREA'].strip(),'discipline':AREA_LABELS.get(r['SG_AREA'].strip()),
                             'position':pos,'index':local_index,'itemCode':r['CO_ITEM'].strip(),
                             'correctAlternative':r['TX_GABARITO'].strip().upper(),
                             'isAnnulled':r.get('IN_ITEM_ABAN','0').strip()=='1',
                             **{k:(float(r[v].replace(',','.')) if r[v].strip() else None) for k,v in PARAMS.items()},
                             'skillCode':r.get('CO_HABILIDADE','').strip() or None})
    return rows


def normalize_text(s):
    return re.sub(r'\s+',' ',str(s or '')).strip()

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--items',type=Path,default=Path('dados/extraidos'))
    ap.add_argument('--json',type=Path,default=Path('dados/processados/textos/questoes_texto_inep.json'))
    ap.add_argument('--out',type=Path,default=Path('dados/processados/dataset_tri.csv'))
    ap.add_argument('--color',action='append',help='Filtra cor; pode repetir. Padrão: todas com PDF.')
    args=ap.parse_args()
    texts=json.loads(args.json.read_text(encoding='utf-8'))
    years={int(x['year']) for x in texts}
    labels=read_item_rows(args.items,years)
    color_filter={COLOR_ALIASES.get(x.upper(),x.upper()) for x in args.color} if args.color else None
    # Index text by exact year/color/day/local question number, preserving all duplicates for review.
    text_index={}
    for q in texts:
        color=q['color']; key=(int(q['year']),color,int(q['day']),int(q['index']))
        text_index.setdefault(key,[]).append(q)
    joined=[]; review=[]
    for r in labels:
        if r['isAnnulled'] or color_filter and r['examColor'] not in color_filter: continue
        key=(r['year'],r['examColor'],r['day'],r['index'])
        candidates=text_index.get(key,[])
        if len(candidates)!=1:
            review.append({**r,'candidate_count':len(candidates),'reason':'no_text_match' if not candidates else 'ambiguous_text_match'})
            continue
        q=candidates[0]
        # If the PDF text explicitly provides five alternatives, enforce the official key exists.
        alts=q.get('alternatives',[])
        alt_letters={a['letter'] for a in alts}
        status=q['alternativeStatus']
        if alt_letters and r['correctAlternative'] not in alt_letters:
            review.append({**r,'candidate_count':1,'reason':'answer_key_not_in_extracted_alternatives'})
            continue
        text=' '.join([normalize_text(q.get('context')),normalize_text(q.get('alternativesIntroduction'))]+
                      [normalize_text(a.get('text')) for a in alts])
        if not text:
            review.append({**r,'candidate_count':1,'reason':'empty_text'}); continue
        joined.append({**r,'title':q['title'],'context':q['context'],'alternatives':json.dumps(alts,ensure_ascii=False),
                       'text':text,'sourcePdf':q['pdf'],'sourcePages':json.dumps(q['sourcePages']),
                       'textExtractionStatus':status,'tokenized_text':None})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fields=['year','examColor','day','examCode','disciplineCode','discipline','position','index','itemCode',
            'correctAlternative','a','b','c','skillCode','title','context','alternatives','text','tokenized_text',
            'sourcePdf','sourcePages','textExtractionStatus']
    with args.out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(joined)
    review_path=args.out.with_name(args.out.stem+'_revisao.csv')
    review_fields=list(dict.fromkeys(k for r in review for k in r)) or ['year','reason']
    with review_path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=review_fields,extrasaction='ignore'); w.writeheader(); w.writerows(review)
    print(f'Linhas aprovadas: {len(joined)} -> {args.out}')
    print(f'Linhas para revisar: {len(review)} -> {review_path}')

if __name__=='__main__': main()
