#!/usr/bin/env python3
"""Substitui o texto extraído pelo texto ENEM.DEV quando o índice é consistente."""
from __future__ import annotations
import argparse,csv,json,re
from pathlib import Path

def area_code(value):
    value=str(value or '').lower()
    if 'matem' in value:return 'MT'
    if 'natureza' in value:return 'CN'
    if 'human' in value:return 'CH'
    if 'lingu' in value:return 'LC'
    return None

def clean(value): return re.sub(r'\s+',' ',str(value or '')).strip()
def api_text(q):
    parts=[q.get('context'),q.get('alternativesIntroduction')]
    parts += [a.get('text') or a.get('texto') for a in q.get('alternatives',[]) if isinstance(a,dict)]
    return ' '.join(clean(x) for x in parts if clean(x))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dataset',type=Path,default=Path('dados/processados/dataset_tri.csv'))
    ap.add_argument('--api',type=Path,default=Path('dados/api_enem_dev'))
    ap.add_argument('--out',type=Path,default=Path('dados/processados/dataset_tri_api.csv'))
    args=ap.parse_args()
    # A API ENEM.DEV usa o mesmo número impresso da prova azul.
    # A área só serve para desempatar variantes de idioma no mesmo índice.
    api={}
    for path in args.api.glob('*.json'):
        for q in json.loads(path.read_text(encoding='utf-8')):
            key=(int(q.get('year',path.stem)),int(q['index']))
            api.setdefault(key,[]).append(q)
    with args.dataset.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    synced=0; ambiguous=0; audit=[]
    for row in rows:
        key=(int(row['year']),int(row['index']))
        candidates=api.get(key,[])
        # A API representa a prova azul regular; rejeite outras aplicações.
        pdf_name=str(row.get('sourcePdf') or '').upper()
        secondary_copy=bool(re.search(r'_2(?:\.PDF)+$',pdf_name))
        regular=not secondary_copy and not any(token in pdf_name for token in ('_P2_', 'PPL', 'REAPLIC', 'DIGITAL'))
        same_area=[q for q in candidates if area_code(q.get('discipline'))==row.get('disciplineCode')]
        same_answer=[q for q in same_area if str(q.get('correctAlternative','')).upper()==str(row.get('correctAlternative','')).upper()]
        if not regular: status='wrong_application'
        elif not candidates: status='missing_api'
        elif not same_area: status='area_mismatch'
        elif not same_answer: status='answer_mismatch'
        elif len(same_answer)!=1: status='ambiguous'
        elif len(same_answer[0].get('alternatives',[]))!=5 or not api_text(same_answer[0]): status='incomplete_api'
        else: status='confirmed'
        if status=='confirmed':
            q=same_answer[0]
            row['pdf_text']=row.get('text','')
            row['context']=q.get('context',''); row['alternativesIntroduction']=q.get('alternativesIntroduction','')
            row['alternatives']=json.dumps(q.get('alternatives',[]),ensure_ascii=False)
            row['text']=api_text(q); row['api_source']=f"{q.get('year')}/{q.get('index')}"
            row['api_match']='confirmed'; synced+=1
        else:
            row['api_source']=''; row['api_match']=status; ambiguous+=1
        audit.append({'year':row['year'],'index':row['index'],'itemCode':row['itemCode'],'api_match':row['api_match'],'candidate_count':len(candidates),'sourcePdf':row.get('sourcePdf','')})
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fields=list(rows[0]) if rows else []
    with args.out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
    audit_path=args.out.with_name(args.out.stem+'_auditoria.csv')
    with audit_path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(audit[0]) if audit else ['year']);w.writeheader();w.writerows(audit)
    print(f'API sincronizada por ano+índice: {synced}; sem sincronização: {ambiguous} -> {args.out}')

if __name__=='__main__': main()
