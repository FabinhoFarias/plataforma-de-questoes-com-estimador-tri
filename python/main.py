#!/usr/bin/env python3
"""Pipeline completo local: reduzir ZIPs, extrair texto, montar dataset e treinar."""
from __future__ import annotations
import argparse, subprocess, sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
PYDIR=ROOT/'python'

def run(args:list[str]):
    print('\n$', ' '.join(args), flush=True)
    subprocess.run(args,cwd=ROOT,check=True)

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,default=Path('dados/microdados'))
    ap.add_argument('--reduced',type=Path,default=Path('dados/extraidos'))
    ap.add_argument('--color',default='AZUL')
    ap.add_argument('--skip-reduce',action='store_true',help='Usa arquivos reduzidos que já existem')
    ap.add_argument('--skip-extract',action='store_true',help='Reutiliza JSON de texto existente')
    ap.add_argument('--skip-embeddings',action='store_true',help='Reutiliza dataset com embeddings já calculados')
    ap.add_argument('--include-ambiguous',action='store_true',help='Inclui linhas ambíguas no CSV; o treino usa somente exact')
    ap.add_argument('--force-embeddings',action='store_true',help='Recalcula embeddings mesmo se o CSV já existir')
    ap.add_argument('--skip-train',action='store_true')
    ap.add_argument('--delete-zips',action='store_true',help='Apaga ZIP após extração válida')
    ap.add_argument('--ocr',action='store_true',help='Aciona OCR; requer Tesseract e idiomas por+eng')
    args=ap.parse_args()
    input_dir=(ROOT/args.input).resolve() if not args.input.is_absolute() else args.input
    reduced_dir=(ROOT/args.reduced).resolve() if not args.reduced.is_absolute() else args.reduced
    process=ROOT/'dados'/'processados'
    text_dir=process/'textos'; json_path=text_dir/'questoes_texto_inep.json'
    dataset=process/'dataset_tri.csv'
    enriched_dataset=process/'dataset_tri_enriquecido.csv'
    embedded_dataset=process/'dataset_com_embeddings.csv'
    colors=[args.color.upper()]

    if not args.skip_reduce:
        cmd=[sys.executable,str(PYDIR/'extrair_pacotes_inep.py'),'--input',str(input_dir),'--output',str(reduced_dir)]
        for color in colors: cmd += ['--color',color]
        if args.delete_zips: cmd += ['--delete-zips']
        run(cmd)
    text_is_valid=json_path.exists() and json_path.stat().st_size > 500 and not json_path.read_bytes()[:40].startswith(b'version https://git-lfs.github.com')
    if not args.skip_extract or not text_is_valid:
        if args.skip_extract and not text_is_valid:
            print(f'JSON de texto ausente/vazio; regenerando {json_path}', flush=True)
        cmd=[sys.executable,str(PYDIR/'extrair_texto_questoes.py'),'--input',str(reduced_dir),'--output',str(text_dir)]
        for color in colors: cmd += ['--color',color]
        if args.ocr: cmd += ['--ocr']
        run(cmd)
    mount=[sys.executable,str(PYDIR/'montar_dataset_tri.py'),'--items',str(reduced_dir),'--json',str(json_path),'--out',str(dataset),'--color',args.color]
    if args.include_ambiguous: mount.append('--include-ambiguous')
    run(mount)
    run([sys.executable,'-m','python.enriquecer_dataset_questoes','--dataset',str(dataset),'--out',str(enriched_dataset)])
    embedded_is_valid=False
    if embedded_dataset.exists():
        head=embedded_dataset.read_bytes()[:1000]
        embedded_is_valid=(not head.startswith(b'version https://git-lfs.github.com') and b'embedding' in head.splitlines()[0])
    if not args.skip_embeddings and (args.force_embeddings or not embedded_is_valid):
        run([sys.executable,'-m','python.tokenizar_dataset','--csv',str(enriched_dataset),'--out',str(embedded_dataset)])
    elif not args.skip_embeddings:
        print(f'Embeddings já existentes; reutilizando {embedded_dataset}', flush=True)
    if not args.skip_train:
        run([sys.executable,'-m','python.treinar_modelo','--csv',str(embedded_dataset),'--out',str(ROOT/'dados'/'modelos')])

if __name__=='__main__': main()
