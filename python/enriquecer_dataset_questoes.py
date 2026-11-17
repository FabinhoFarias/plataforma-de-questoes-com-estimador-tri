#!/usr/bin/env python3
"""Cruza o dataset TRI com a base QuestõesEnem e adiciona metadados pedagógicos."""
from __future__ import annotations
import argparse,csv,json,re,unicodedata
from collections import defaultdict, Counter
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

def application(value):
    value=norm(value)
    if re.search(r' 2 pdf(?: pdf)?$',value): return 'secondary_unknown'
    if any(x in value for x in ('ppl','reaplicacao',' p2 ')) or value.endswith(' p2'): return 'ppl'
    if 'digital' in value: return 'digital'
    if any(x in value for x in ('regular',' p1 ','enem','caderno')): return 'regular'
    return None

def alternatives(row):
    value=row.get('alternativas') or row.get('alternatives') or []
    if isinstance(value,str):
        try: value=json.loads(value)
        except json.JSONDecodeError: return []
    return value if isinstance(value,list) else []

def answer(row):
    for alt in alternatives(row):
        if isinstance(alt,dict) and alt.get('e_correta') is True:
            return str(alt.get('letra') or alt.get('letter') or '').upper()
    return None

def curated_text(row):
    parts=[row.get('contexto'),row.get('introducao_alternativas')]
    parts += [a.get('texto') or a.get('text') for a in alternatives(row) if isinstance(a,dict)]
    return ' '.join(re.sub(r'\s+',' ',str(part or '')).strip() for part in parts if part).strip()

def alternative_agreement(pdf_row, curated_row):
    left=[norm(a.get('text') or a.get('texto')) for a in alternatives(pdf_row) if isinstance(a,dict)]
    right=[norm(a.get('texto') or a.get('text')) for a in alternatives(curated_row) if isinstance(a,dict)]
    if len(left)!=5 or len(right)!=5: return 0
    return sum(SequenceMatcher(None,a,b,autojunk=False).ratio()>=.72 for a,b in zip(left,right))

def alternative_scores(pdf_row, curated_row):
    left=[norm(a.get('text') or a.get('texto')) for a in alternatives(pdf_row) if isinstance(a,dict)]
    right=[norm(a.get('texto') or a.get('text')) for a in alternatives(curated_row) if isinstance(a,dict)]
    if len(left)!=5 or len(right)!=5: return [],0
    scores=[]
    for a,b in zip(left,right):
        matcher=SequenceMatcher(None,a,b,autojunk=False)
        scores.append(matcher.ratio() if matcher.quick_ratio()>=.72 else 0.0)
    return scores,sum(len(x) for x in right)

def alternative_grams(row):
    grams=set()
    for alt in alternatives(row):
        if not isinstance(alt,dict): continue
        value=norm(alt.get('texto') or alt.get('text'))
        if len(value)<15: continue
        grams.update(('alt',*gram) for gram in shingles(value))
        compact=value.replace(' ','')
        grams.update(('char',compact[i:i+7]) for i in range(0,len(compact)-6,3))
    return grams

def shingles(value):
    words=value.split()
    return set(zip(words,words[1:],words[2:])) if len(words)>=3 else set()

def area_code(value):
    value=norm(value)
    for code,terms in {'CH':('human','historia','geografia','sociologia','filosofia'),
                       'CN':('natureza','fisica','quimica','biologia'),
                       'LC':('linguagem','portugues','literatura','ingles','espanhol','artes'),
                       'MT':('matematica',)}.items():
        if any(term in value for term in terms): return code
    return None

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--dataset',type=Path,default=Path('dados/processados/dataset_tri.csv'))
    ap.add_argument('--source',type=Path,default=Path('dados/QuestoesEnem'))
    ap.add_argument('--out',type=Path,default=Path('dados/processados/dataset_tri_enriquecido.csv'))
    ap.add_argument('--fuzzy-threshold',type=float,default=.88)
    args=ap.parse_args()
    rich=[]
    for path in args.source.rglob('*.json'):
        for row in load_json_records(path):
            if row.get('banca') and 'ENEM' not in str(row['banca']).upper(): continue
            key=rich_text(row)
            if key and len(key)>50: rich.append((key,rich_context(row),row,path,
                                                 area_code(row.get('grande_area') or row.get('disciplina') or str(path))))
    exact=defaultdict(list); context_exact=defaultdict(list); index=defaultdict(list); alt_index=defaultdict(list)
    for i,(key,context,row,path,area) in enumerate(rich):
        exact[key].append(i)
        if context: context_exact[context].append(i)
        for gram in shingles(context or key): index[gram].append(i)
        for gram in alternative_grams(row): alt_index[gram].append(i)
    with args.dataset.open(encoding='utf-8-sig',newline='') as f: rows=list(csv.DictReader(f))
    enriched=[]; counts={'confirmed':0,'unmatched':0,'ambiguous':0}; cache={}; audit=[]; pairs=[]
    for row in rows:
        key=norm(row.get('text')); context=norm(row.get('context'))
        lookup=(key,context,row.get('disciplineCode'))
        if lookup not in cache:
            area=row.get('disciplineCode')
            ids=exact.get(key,[]) or context_exact.get(context,[])
            grams=shingles(context or key)
            hits=Counter(i for gram in grams for i in index.get(gram,())
                         if rich[i][4] in (None,area))
            alt_hits=Counter(i for gram in alternative_grams(row)
                             for i in alt_index.get(gram,()) if len(alt_index[gram])<=80
                             and rich[i][4] in (None,area))
            candidate_ids=set(i for i in ids if rich[i][4] in (None,area))
            candidate_ids.update(i for i,_ in hits.most_common(10))
            candidate_ids.update(i for i,_ in alt_hits.most_common(15))
            accepted=[]
            for i in candidate_ids:
                _,_,candidate,path,_=rich[i]
                source_app=application(str(candidate.get('banca') or '')+' '+str(candidate.get('title') or ''))
                pdf_app=application(row.get('sourcePdf'))
                if source_app!=pdf_app: continue
                if candidate.get('ano') and str(candidate['ano'])!=str(row.get('year')): continue
                if answer(candidate)!=str(row.get('correctAlternative') or '').upper(): continue
                alt_scores,alt_length=alternative_scores(row,candidate)
                if not alt_scores: continue
                if min(alt_scores)<.72: continue
                candidate_context=rich[i][1] or rich[i][0]
                overlap=len(grams & shingles(candidate_context))/max(1,len(grams))
                similarity=SequenceMatcher(None,(context or key)[:1000],candidate_context[:1000],autojunk=False).ratio()
                context_score=1.0 if key==rich[i][0] or context==rich[i][1] else .6*overlap+.4*similarity
                agreed=sum(value>=.72 for value in alt_scores)
                strong_alts=all(value>=.82 for value in alt_scores) and alt_length>=70
                classic=context_score>=args.fuzzy_threshold and agreed==5
                recovered=strong_alts and context_score>=.30
                if not (classic or recovered): continue
                evidence=.5*context_score+.5*sum(alt_scores)/5
                accepted.append((evidence,context_score,agreed,rich[i],
                                 'alternativas' if recovered and not classic else 'texto_alternativas'))
            accepted.sort(key=lambda x:(x[0],x[1]),reverse=True)
            if accepted:
                first=accepted[0]
                distinct={str(x[3][2].get('id_externo') or x[3][3]) for x in accepted
                          if first[0]-x[0]<.05}
                cache[lookup]=(first[3],first[1],'ambiguous' if len(distinct)>1 else 'confirmed',first[2],first[4])
            else: cache[lookup]=(None,0,'unmatched',0,'')
        match,score,status,agreed,method=cache[lookup]
        row['pdf_text']=row.get('pdf_text') or row.get('text','')
        if match and status=='confirmed':
            _,_,meta,path,_=match; counts[status]+=1
            for field in FIELDS: row[field]=meta.get(field)
            # Regra de fonte: texto ENEM.DEV tem prioridade quando sincronizado.
            # QuestoesEnem só substitui o texto quando a API não trouxe a questão.
            if row.get('api_match') == 'confirmed':
                row['text_source']='ENEM.DEV'
            else:
                row['text']=curated_text(meta)
                row['context']=meta.get('contexto') or ''
                row['alternatives']=json.dumps(alternatives(meta),ensure_ascii=False)
                row['text_source']='QuestoesEnem'
            row['metadata_source']=str(path); row['metadata_match_score']=round(score,4)
            row['metadata_match_status']='confirmed'
            row['metadata_application']=application(str(meta.get('banca') or '')+' '+str(meta.get('title') or ''))
            row['metadata_match_method']=method
            pairs.append({'year':row.get('year'),'itemCode':row.get('itemCode'),
                          'index':row.get('index'),'sourcePdf':row.get('sourcePdf'),
                          'correctAlternative':row.get('correctAlternative'),
                          'id_externo':row.get('id_externo'),'metadata_source':str(path),
                          'application':row['metadata_application'],
                          'context_score':round(score,4),'alternatives_agree':agreed,'method':method,
                          'pdf_context':row.get('pdf_text','')[:1200],
                          'curated_context':meta.get('contexto','')[:1200]})
        else:
            if row.get('api_match') == 'confirmed':
                row['text_source']='ENEM.DEV'
                row['metadata_match_status']='api_only'
                row['metadata_source']=''; row['metadata_match_score']=0
                row['metadata_application']=''; row['metadata_match_method']=''
                counts['confirmed']+=1
                enriched.append(row)
                continue
            counts[status]+=1
            for field in FIELDS: row[field]=None
            row['metadata_source']=''; row['metadata_match_score']=0; row['metadata_match_status']='unmatched'
            row['text_source']='pdf_unconfirmed'
            row['metadata_application']=''
            row['metadata_match_method']=''
        row['metadata_alternatives_agree']=agreed
        if status!='confirmed':
            audit.append({'year':row.get('year'),'itemCode':row.get('itemCode'),
                          'index':row.get('index'),'sourcePdf':row.get('sourcePdf'),
                          'status':status,'candidate_score':round(score,4)})
        enriched.append(row)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(k for item in enriched for k in item)) if enriched else []
    with args.out.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(enriched)
    audit_path=args.out.with_name(args.out.stem+'_auditoria.csv')
    with audit_path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=['year','itemCode','index','sourcePdf','status','candidate_score'])
        w.writeheader(); w.writerows(audit)
    pair_path=args.out.with_name(args.out.stem+'_pares_confirmados.csv')
    with pair_path.open('w',encoding='utf-8-sig',newline='') as f:
        fields=['year','itemCode','index','sourcePdf','correctAlternative','id_externo',
                'metadata_source','application','context_score','alternatives_agree','method',
                'pdf_context','curated_context']
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader(); w.writerows(pairs)
    print(f'{len(enriched)} linhas enriquecidas -> {args.out}')
    print('Pareamento:',counts)

if __name__=='__main__': main()
