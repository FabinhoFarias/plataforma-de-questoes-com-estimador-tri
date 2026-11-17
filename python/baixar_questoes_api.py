#!/usr/bin/env python3
"""Baixa questões ENEM.DEV por índice, de 2009 a 2023."""
from __future__ import annotations
import argparse, json, time
from pathlib import Path
import requests

BASE='https://api.enem.dev/v1/exams'

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--out',type=Path,default=Path('dados/api_enem_dev'))
    ap.add_argument('--start-year',type=int,default=2009)
    ap.add_argument('--end-year',type=int,default=2023)
    ap.add_argument('--max-index',type=int,default=180)
    ap.add_argument('--batch-size',type=int,default=50,help='Questões por requisição; a API aceita lotes paginados')
    ap.add_argument('--timeout',type=float,default=30)
    ap.add_argument('--retries',type=int,default=5)
    args=ap.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    session=requests.Session(); session.headers.update({'User-Agent':'EstimadorTriEnem/1.0'})
    for year in range(args.start_year,args.end_year+1):
        path=args.out/f'{year}.json'
        existing={}
        if path.exists():
            try: existing={str(x['index']):x for x in json.loads(path.read_text(encoding='utf-8'))}
            except (OSError,ValueError,TypeError): existing={}
        for offset in range(0,args.max_index,args.batch_size):
            url=f'{BASE}/{year}/questions'
            params={'limit':min(args.batch_size,args.max_index-offset),'offset':offset}
            for attempt in range(args.retries):
                try:
                    response=session.get(url,params=params,timeout=args.timeout)
                    if response.status_code==404: break
                    response.raise_for_status(); item=response.json()
                    batch=item.get('questions',[]) if isinstance(item,dict) else item
                    if not isinstance(batch,list): raise ValueError('resposta sem lista questions')
                    for question in batch:
                        if isinstance(question,dict) and 'index' in question:
                            existing[str(question['index'])]=question
                    print(f'{year}: lote offset={offset} recebido ({len(batch)} questões)',flush=True); break
                except (requests.RequestException,ValueError) as exc:
                    if attempt+1==args.retries: print(f'{year}/offset={offset}: falhou após {args.retries}: {exc}',flush=True)
                    else: time.sleep(min(2**attempt,8))
            ordered=sorted(existing.values(),key=lambda x:int(x.get('index',0)))
            path.write_text(json.dumps(ordered,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
            time.sleep(.1)
        ordered=sorted(existing.values(),key=lambda x:int(x.get('index',0)))
        path.write_text(json.dumps(ordered,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        print(f'{year}: {len(ordered)} questões -> {path}',flush=True)

if __name__=='__main__': main()
