#!/usr/bin/env python3
"""Cruza o dataset TRI com a base QuestõesEnem e adiciona metadados pedagógicos."""
from __future__ import annotations
import argparse,csv,json,re,unicodedata
from difflib import SequenceMatcher
from pathlib import Path

FIELDS=('assunto','competencia','habilidade','dificuldade','id_externo','grande_area','disciplina')

def load_json_records(path:Path):
    raw=path.read_text(encoding='utf-8-sig')
    decoder=json.JSONDecoder(); pos=0; records=[]
    while pos < len(raw):
        while pos < len(raw) and raw[pos].isspace(): pos += 1
        if pos >= len(raw): break
        try: value,end=decoder.raw_decode(raw,pos)
        except json.JSONDecodeError: break
        pos=end
        if isinstance(value,list): records.extend(x for x in value if isinstance(x,dict))
        elif isinstance(value,dict): records.append(value)
    return records

def norm(text):
    text=unicodedata.normalize('NFKD',str(text or ''))
    text=''.join(c for c in text if not unicodedata.combining(c)).lower()
    return re.sub(r'[^a-z0-9]+',' ',text).strip()

def rich_text(row):
    parts=[row.get('contexto'),row.get('introducao_alternativas')]
    parts += [a.get('texto') for a in row.get('alternativas',[]) if isinstance(a,dict)]
    return norm(' '.join(str(x or '') for x in parts))

def rich_context(row):
    return norm(row.get('contexto'))

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dataset',type=Path,default=Path('dados/processados/dataset_tri.csv'))
    ap.add_argument('--source',type=Path,default=Path('dados/QuestoesEnem'))
    ap.add_argument('--out',type=Path,default=Path('dados/processados/dataset_tri_enriquecido.csv'))
    ap.add_argument('--fuzzy-threshold',type=float,default=.72)
    args=ap.parse_args()
    rich=[]
    for path in args.source.rglob('*.json'):
        for row in load_json_records(path):
            if row.get('banca') and 'ENEM' not in str(row['banca']).upper(): continue
            key=rich_text(row)
            if key: rich.append((key,row,path))
    exact={}; context_exact={}; prefix_index={}
    for key,row,path in rich: exact.setdefault(key,[]).append((row,path))
    for key,row,path in rich:
        ckey=rich_context(row)
        if ckey:
            context_exact.setdefault(ckey,[]).append((row,path))
            prefix_index.setdefault(ckey[:80],[]).append((row,path))
    with args.dataset.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    enriched=[]; counts={'exact':0,'fuzzy':0,'unmatched':0,'ambiguous':0}
    for row in rows:
        key=norm(row.get('text'))
        candidates=exact.get(key,[])
        if not candidates and row.get('context'):
            ckey=norm(row.get('context'))
            candidates=context_exact.get(ckey,[])
            if not candidates:
                candidates=prefix_index.get(ckey[:80],[])
        score=1.0; status='exact'
        if len(candidates)==1: match=candidates[0]
        elif len(candidates)>1:
            match=candidates[0]; status='ambiguous'; counts['ambiguous']+=1
        else:
            # Restrict fuzzy search to records with the same discipline when possible.
            pool=candidates or prefix_index.get(key[:80],[])
            if row.get('disciplineCode'):
                pool=[item for item in pool if norm(row.get('disciplineCode')) in norm(item[0].get('disciplina'))]
            best=None
            for candidate in pool:
                s=SequenceMatcher(None,key,candidate[0]).ratio()
                if best is None or s>best[0]: best=(s,candidate)
            if best and best[0] >= args.fuzzy_threshold:
                score,match=best; status='fuzzy'
            else: match=None; status='unmatched'
        if match:
            meta,path=match; counts[status]+=1
            for field in FIELDS: row[field]=meta.get(field)
            row['metadata_source']=str(path); row['metadata_match_score']=round(score,4); row['metadata_match_status']=status
        else:
            counts['unmatched']+=1
            for field in FIELDS: row[field]=None
            row['metadata_source']=''; row['metadata_match_score']=0; row['metadata_match_status']='unmatched'
        enriched.append(row)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fields=list(enriched[0]) if enriched else []
    with args.out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(enriched)
    print(f'{len(enriched)} linhas enriquecidas -> {args.out}')
    print('Pareamento:',counts)

if __name__=='__main__': main()
