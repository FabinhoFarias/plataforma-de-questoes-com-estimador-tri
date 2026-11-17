#!/usr/bin/env python3
"""Identifica CO_PROVA de cada PDF azul comparando gabaritos oficiais com ITENS_PROVA.

Coloque os PDFs dos gabaritos em dados/gabaritos/<ano>/. O nome deve indicar
P1/regular/impresso, P2/reaplicacao/PPL ou digital, e D1/D2 ou dia 1/2.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import subprocess
import urllib.request
from collections import defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import pymupdf

from python.extrair_texto_questoes import pdf_identity
from python.montar_dataset_tri import area_for_index, item_exam_coordinates


def version(name: str) -> str:
    name=name.upper()
    if 'DIGITAL' in name: return 'digital'
    if re.search(r'(?:^|[_-])P2(?:[_-]|$)|REAPLIC|PPL|2[ªA]?[_ -]?APL|_2\.PDF|20\d{2}_2_DIA',name): return 'p2'
    return 'p1'


def day(name: str) -> int | None:
    name=name.upper()
    if re.search(r'(?:^|[_-])(?:D1|DIA[_ -]?0?1|SAB(?:ADO)?)(?:[_ .-]|$)',name): return 1
    if re.search(r'(?:^|[_-])(?:D2|DIA[_ -]?0?2|DOM(?:INGO)?)(?:[_ .-]|$)',name): return 2
    if re.search(r'(?:^|[_-])1[_ -]?DIA|(?:CAD|CADERNO)[_ -]?0?1(?:[_ .-]|$)',name): return 1
    if re.search(r'(?:^|[_-])2[_ -]?DIA|(?:CAD|CADERNO)[_ -]?0?7(?:[_ .-]|$)',name): return 2
    return None


def blue_key(name: str) -> bool:
    up=name.upper()
    return 'AZUL' in up or bool(re.search(r'(?:^|_)CD(?:0?1|0?7)(?:[_.-]|$)',up))


class PdfLinks(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls=[]; self.current=None

    def handle_starttag(self,tag,attrs):
        if tag=='a':
            href=dict(attrs).get('href','')
            self.current=[href,''] if href.lower().split('?')[0].endswith('.pdf') else None

    def handle_data(self,data):
        if self.current is not None: self.current[1]+=data

    def handle_endtag(self,tag):
        if tag=='a' and self.current is not None:
            self.urls.append(tuple(self.current)); self.current=None


def download_keys(year: int, target: Path) -> int:
    """Descobre gabaritos no índice oficial do INEP; falha de rede não inventa mapeamentos."""
    page=f'https://www.gov.br/inep/pt-br/areas-de-atuacao/avaliacao-e-exames-educacionais/enem/provas-e-gabaritos/{year}'
    try:
        with urllib.request.urlopen(page,timeout=20) as response: html=response.read()
    except Exception as exc:
        try:
            html=subprocess.run(['curl','-fsSL','--retry','2','--max-time','30',page],
                                check=True,capture_output=True).stdout
        except (OSError,subprocess.CalledProcessError) as curl_exc:
            print(f'{year}: índice de gabaritos indisponível: {exc}; curl: {curl_exc}',flush=True)
            return 0
    links=PdfLinks(); links.feed(html.decode('utf-8',errors='replace')); urls=set()
    for href,label in links.urls:
        name=Path(urlparse(href).path).name
        if 'download.inep.gov.br' not in urlparse(href).netloc or not name.lower().endswith('.pdf'): continue
        if not re.search(r'gab|(?:^|_)gb(?:_|$)',name,re.I) and 'gabarito' not in label.lower(): continue
        if not blue_key(name) and not (year==2009 and name.lower().startswith('gabarito_dia')): continue
        urls.add(href)
    if year==2009:
        base='https://download.inep.gov.br/educacao_basica/enem/gabaritos/2009/'
        urls.update(base+f'gabarito_dia{day_no}.pdf' for day_no in (1,2))
    if year==2015:
        base='https://download.inep.gov.br/educacao_basica/enem/gabaritos/2015/'
        urls.update(base+f'GAB_ENEM_2015_2aAPLICACAO_DIA_{day_no}_{book}_AZUL.pdf'
                    for day_no,book in (('01','01'),('02','07')))
    count=0; target.mkdir(parents=True,exist_ok=True)
    for url in sorted(urls):
        name=Path(urlparse(url).path).name; path=target/name
        if path.exists() and path.stat().st_size>1000: count+=1; continue
        try:
            with urllib.request.urlopen(url,timeout=30) as response: data=response.read()
            if data.startswith(b'%PDF'):
                path.write_bytes(data); count+=1
        except Exception as exc:
            try:
                subprocess.run(['curl','-fsSL','--retry','2','--max-time','60','-o',str(path),url],
                               check=True,capture_output=True)
                if path.read_bytes()[:4]==b'%PDF': count+=1
                else: path.unlink(missing_ok=True)
            except (OSError,subprocess.CalledProcessError) as curl_exc:
                path.unlink(missing_ok=True)
                print(f'{year}: não foi possível baixar {name}: {exc}; curl: {curl_exc}',flush=True)
    return count


def answer_key(path: Path) -> dict[int,str]:
    """Lê pares número/letra na mesma linha visual, inclusive tabelas em colunas."""
    result={}; conflicts=set()
    with pymupdf.open(path) as doc:
        for page in doc:
            blue_headers=[w[0] for w in page.get_text('words') if w[4].upper()=='GAB_AZUL']
            blue_x=blue_headers[0] if blue_headers and '2009' in path.parts else None
            lines=defaultdict(list)
            for word in page.get_text('words'):
                x0,y0,x1,y1,value,*_=word
                lines[round((y0+y1)/4)*2].append((x0,x1,value.strip().upper()))
            for words in lines.values():
                words.sort()
                for i,(x0,x1,value) in enumerate(words):
                    if not re.fullmatch(r'0?[1-9]|[1-9]\d|1[0-7]\d|180',value): continue
                    number=int(value)
                    nearby=[(a,b,t) for a,b,t in words[i+1:] if 0<=a-x1<110 and re.fullmatch('[A-E]',t)
                            and (blue_x is None or 5<a-blue_x<40)]
                    if not nearby: continue
                    letter=nearby[0][2]
                    if number in result and result[number]!=letter: conflicts.add(number)
                    else: result[number]=letter
    for number in conflicts: result.pop(number,None)
    return result


def item_groups(path: Path) -> dict[tuple[str,str],dict[int,tuple[str,str,tuple[str,str,str]]]]:
    groups=defaultdict(dict)
    with path.open(encoding='latin1',newline='') as f:
        for row in csv.DictReader(f,delimiter=';'):
            if row.get('TX_COR','').strip().upper()!='AZUL': continue
            if row.get('TP_LINGUA','').strip(): continue
            area=row['SG_AREA'].strip(); code=row['CO_PROVA'].strip()
            _,index=item_exam_coordinates(int(re.search(r'\d{4}',path.name).group()),area,int(row['CO_POSICAO']))
            if index is None: continue
            groups[(area,code)][index]=(row['TX_GABARITO'].strip().upper(),row['CO_ITEM'].strip(),
                                          tuple(row[f].strip() for f in ('NU_PARAM_A','NU_PARAM_B','NU_PARAM_C')))
    return groups


def map_year(year_dir: Path, key_dir: Path) -> list[dict]:
    year=int(year_dir.name)
    table=next((p for p in (year_dir/'itens').glob('*.csv')),None)
    if not table: return []
    groups=item_groups(table); result=[]
    proofs=[]
    for pdf in sorted((year_dir/'prova_gabarito').glob('*.pdf')):
        identity=pdf_identity(pdf.name,year)
        if identity and identity['color']=='AZUL': proofs.append(identity)
    for pdf in proofs:
        matching_keys=[p for p in key_dir.rglob('*.pdf') if day(p.name)==pdf['day'] and version(p.name)==version(pdf['pdf'])
                       and (blue_key(p.name) or year==2009 and p.name.lower().startswith('gabarito_dia'))]
        if len(matching_keys)>1 and version(pdf['pdf'])=='digital':
            matching_keys=[p for p in matching_keys if 'INGLES' in p.name.upper() or 'INGL' in p.name.upper()] or matching_keys
        if len(matching_keys)!=1: continue
        answers=answer_key(matching_keys[0])
        if len(answers)<45: continue
        for area in ('CH','CN','LC','MT'):
            area_answers={pos:letter for pos,letter in answers.items() if area_for_index(year,pos)==area}
            if len(area_answers)<25: continue
            candidates=[]
            for (candidate_area,code),items in groups.items():
                if candidate_area!=area: continue
                common=[(pos,letter) for pos,letter in area_answers.items() if pos in items and items[pos][0] in 'ABCDE']
                if len(common)<25: continue
                agreement=sum(items[pos][0]==letter for pos,letter in common)/len(common)
                candidates.append((agreement,len(common),code,items))
            candidates.sort(reverse=True)
            if not candidates: continue
            best=candidates[0]
            equivalent=[c for c in candidates if c[3]==best[3]]
            competitors=[c for c in candidates if c[3]!=best[3]]
            second=competitors[0][0] if competitors else 0.0
            if best[0]<.95 or best[0]-second<.15: continue
            canonical=min((c[2] for c in equivalent),key=int)
            result.append({'year':year,'pdf':pdf['pdf'],'area':area,'examCode':canonical,
                           'equivalentCodes':sorted((c[2] for c in equivalent),key=int),
                           'agreement':round(best[0],4),'compared':best[1],
                           'runnerUpAgreement':round(second,4),'answerKey':str(matching_keys[0])})
    return result


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--items',type=Path,default=Path('dados/extraidos'))
    parser.add_argument('--gabaritos',type=Path,default=Path('dados/gabaritos'))
    parser.add_argument('--out',type=Path,default=Path('dados/processados/mapa_co_prova.json'))
    parser.add_argument('--download',action='store_true',help='Baixa gabaritos azuis do índice oficial do INEP')
    args=parser.parse_args(); mappings=[]
    for year_dir in sorted(args.items.glob('[12][09][0-9][0-9]')):
        if not any((identity:=pdf_identity(p.name,int(year_dir.name))) and identity['color']=='AZUL'
                   for p in (year_dir/'prova_gabarito').glob('*.pdf')):
            continue
        key_dir=args.gabaritos/year_dir.name
        if args.download: download_keys(int(year_dir.name),key_dir)
        if key_dir.exists(): mappings.extend(map_year(year_dir,key_dir))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(mappings,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(mappings)} mapeamentos verificados por gabarito -> {args.out}',flush=True)


if __name__=='__main__': main()
