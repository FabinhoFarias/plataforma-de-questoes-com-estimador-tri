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


def area_for_index(year:int, index:int):
    """Área que ocupa o número impresso, conforme a ordem da edição."""
    if not 1 <= index <= 180:
        return None
    if year == 2009:
        order=('CN','CH','LC','MT')
    elif year <= 2015:
        order=('CH','CN','LC','MT')
    else:
        order=('LC','CH','CN','MT')
    return order[(index-1)//45]


def item_exam_coordinates(year:int, area:str, position:int):
    """Retorna dia e número impresso para uma posição oficial do item."""
    if year == 2017:
        # Em 2017 CO_POSICAO reinicia por área; os 10 itens de língua estrangeira
        # (posições 1-10) são variantes das questões impressas 1-5.
        if area == 'LC':
            return (1, position if position <= 5 else position-5) if position <= 50 else (None,None)
        offsets={'CH':45,'CN':90,'MT':135}
        day=1 if area=='CH' else 2
        return (day,offsets[area]+position) if area in offsets and 1 <= position <= 45 else (None,None)

    day=(1 if area in ('CH','CN') else 2) if year <= 2015 else (1 if area in ('LC','CH') else 2)
    # From 2009 through 2016 and again from 2018 onward, CO_POSICAO is the
    # printed global position. The dataset files confirm each year's ranges.
    return day,position


def read_item_rows(root:Path, years:set[int]):
    rows=[]
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
                area=r['SG_AREA'].strip()
                day,local_index=item_exam_coordinates(year,area,pos)
                rows.append({'year':year,'examColor':color,'day':day,'examCode':r['CO_PROVA'].strip(),
                             'disciplineCode':area,'discipline':AREA_LABELS.get(area),
                             'position':pos,'index':local_index,'itemCode':r['CO_ITEM'].strip(),
                             'correctAlternative':r['TX_GABARITO'].strip().upper(),
                             'languageCode':r.get('TP_LINGUA','').strip(),
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
    ap.add_argument('--include-ambiguous',action='store_true',help='Inclui candidatos ambíguos e marca a qualidade do pareamento')
    args=ap.parse_args()
    texts=json.loads(args.json.read_text(encoding='utf-8'))
    years={int(x['year']) for x in texts}
    labels=read_item_rows(args.items,years)
    color_filter={COLOR_ALIASES.get(x.upper(),x.upper()) for x in args.color} if args.color else None
    # Index by year/color/day/area/printed question; duplicates remain visible for review.
    text_index={}
    for q in texts:
        year=int(q['year']); area=area_for_index(year,int(q['index']))
        color=q['color']; key=(year,color,int(q['day']),area,int(q['index']))
        text_index.setdefault(key,[]).append(q)
    code_counts={}
    for row in labels:
        key=(row['year'],row['examColor'],row['disciplineCode'])
        code_counts.setdefault(key,set()).add(row['examCode'])
    joined=[]; review=[]
    for r in labels:
        if r['isAnnulled'] or color_filter and r['examColor'] not in color_filter: continue
        if r['day'] is None or r['index'] is None:
            review.append({**r,'candidate_count':0,'reason':'unsupported_exam_position_mapping'}); continue
        if r['languageCode']:
            review.append({**r,'candidate_count':0,'reason':'language_variant_requires_exact_mapping'}); continue
        if len(code_counts[(r['year'],r['examColor'],r['disciplineCode'])]) != 1 and not args.include_ambiguous:
            review.append({**r,'candidate_count':0,'reason':'multiple_exam_codes_for_area_need_caderno_mapping'}); continue
        key=(r['year'],r['examColor'],r['day'],r['disciplineCode'],r['index'])
        candidates=text_index.get(key,[])
        if len(candidates)!=1 and not args.include_ambiguous:
            review.append({**r,'candidate_count':len(candidates),'reason':'no_text_match' if not candidates else 'ambiguous_text_match'})
            continue
        if not candidates:
            review.append({**r,'candidate_count':0,'reason':'no_text_match'}); continue
        for q in candidates:
            if q.get('alternativeStatus') != 'five_markers_detected':
                review.append({**r,'candidate_count':len(candidates),'reason':'text_or_alternatives_need_visual_review'}); continue
            alts=q.get('alternatives',[])
            alt_letters={a['letter'] for a in alts}
            status=q['alternativeStatus']
            if alt_letters and r['correctAlternative'] not in alt_letters:
                review.append({**r,'candidate_count':len(candidates),'reason':'answer_key_not_in_extracted_alternatives'}); continue
            text=' '.join([normalize_text(q.get('context')),normalize_text(q.get('alternativesIntroduction'))]+[normalize_text(a.get('text')) for a in alts])
            if not text:
                review.append({**r,'candidate_count':len(candidates),'reason':'empty_text'}); continue
            joined.append({**r,'title':q['title'],'context':q['context'],'alternatives':json.dumps(alts,ensure_ascii=False),
                           'text':text,'sourcePdf':q['pdf'],'sourcePages':json.dumps(q['sourcePages']),
                           'textExtractionStatus':status,'matchQuality':'ambiguous' if len(candidates)>1 else 'exact',
                           'candidateCount':len(candidates)})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fields=['year','examColor','day','examCode','disciplineCode','discipline','position','index','itemCode',
            'correctAlternative','a','b','c','skillCode','title','context','alternatives','text',
            'sourcePdf','sourcePages','textExtractionStatus','matchQuality','candidateCount']
    with args.out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore'); w.writeheader(); w.writerows(joined)
    review_path=args.out.with_name(args.out.stem+'_revisao.csv')
    review_fields=list(dict.fromkeys(k for r in review for k in r)) or ['year','reason']
    with review_path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=review_fields,extrasaction='ignore'); w.writeheader(); w.writerows(review)
    print(f'Linhas aprovadas: {len(joined)} -> {args.out}')
    print(f'Linhas para revisar: {len(review)} -> {review_path}')

if __name__=='__main__': main()
