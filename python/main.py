#!/usr/bin/env python3
"""Pipeline completo local: reduzir ZIPs, extrair texto, montar dataset e treinar."""
from __future__ import annotations
import argparse, subprocess, sys, json
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
    ap.add_argument('--skip-grid-search',action='store_true',help='Treina com hiperparâmetros padrão, sem busca em grade')
    ap.add_argument('--skip-ablation',action='store_true',help='Pula comparação dos modelos com e sem embeddings')
    ap.add_argument('--skip-dimension-study',action='store_true',help='Pula estudo PCA com 6, 125, 245 e 364 dimensões')
    ap.add_argument('--delete-zips',action='store_true',help='Apaga ZIP após extração válida')
    ap.add_argument('--ocr',action='store_true',help='Aciona OCR; requer Tesseract e idiomas por+eng')
    ap.add_argument('--download-gabaritos',action='store_true',help='Tenta baixar gabaritos azuis oficiais para verificar CO_PROVA')
    ap.add_argument('--skip-api',action='store_true',help='Não baixar/sincronizar textos da ENEM.DEV')
    ap.add_argument('--skip-api-download',action='store_true',help='Usa os JSON da API já presentes, sem baixar novamente')
    args=ap.parse_args()
    input_dir=(ROOT/args.input).resolve() if not args.input.is_absolute() else args.input
    reduced_dir=(ROOT/args.reduced).resolve() if not args.reduced.is_absolute() else args.reduced
    process=ROOT/'dados'/'processados'
    text_dir=process/'textos'; json_path=text_dir/'questoes_texto_inep.json'
    dataset=process/'dataset_tri.csv'
    api_dataset=process/'dataset_tri_api.csv'
    enriched_dataset=process/'dataset_tri_enriquecido.csv'
    embedded_dataset=process/'dataset_com_embeddings.csv'
    colors=[args.color.upper()]

    if not args.skip_reduce:
        zips=list(input_dir.glob('microdados_enem_*.zip'))
        if zips:
            cmd=[sys.executable,str(PYDIR/'extrair_pacotes_inep.py'),'--input',str(input_dir),'--output',str(reduced_dir)]
            for color in colors: cmd += ['--color',color]
            if args.delete_zips: cmd += ['--delete-zips']
            run(cmd)
        else:
            item_years={p.parent.parent.name for p in reduced_dir.glob('*/itens/*.csv')}
            pdf_years={p.parent.parent.name for p in reduced_dir.glob('*/prova_gabarito/*.pdf') if args.color.upper() in p.name.upper()}
            if not item_years or not item_years & pdf_years:
                raise FileNotFoundError(f'Sem ZIPs em {input_dir} e sem tabelas de itens e PDFs {args.color} correspondentes em {reduced_dir}.')
            print(f'Sem ZIPs originais; usando dados reduzidos de {len(item_years & pdf_years)} ano(s) em {reduced_dir}',flush=True)
    text_is_valid=json_path.exists() and json_path.stat().st_size > 500
    if text_is_valid:
        with json_path.open('rb') as f:
            text_is_valid=not f.read(40).startswith(b'version https://git-lfs.github.com')
    if not args.skip_extract or not text_is_valid:
        if args.skip_extract and not text_is_valid:
            print(f'JSON de texto ausente/vazio; regenerando {json_path}', flush=True)
        cmd=[sys.executable,str(PYDIR/'extrair_texto_questoes.py'),'--input',str(reduced_dir),'--output',str(text_dir)]
        for color in colors: cmd += ['--color',color]
        if args.ocr: cmd += ['--ocr']
        run(cmd)
    co_prova_map=process/'mapa_co_prova.json'
    map_cmd=[sys.executable,'-m','python.mapear_co_prova','--items',str(reduced_dir),
             '--gabaritos',str(ROOT/'dados'/'gabaritos'),'--out',str(co_prova_map)]
    if args.download_gabaritos: map_cmd.append('--download')
    run(map_cmd)
    mount=[sys.executable,str(PYDIR/'montar_dataset_tri.py'),'--items',str(reduced_dir),'--json',str(json_path),'--out',str(dataset),'--color',args.color,
           '--co-prova-map',str(co_prova_map)]
    if args.include_ambiguous: mount.append('--include-ambiguous')
    run(mount)
    if not args.skip_api:
        if not args.skip_api_download:
            run([sys.executable,'-m','python.baixar_questoes_api','--out',str(ROOT/'dados'/'api_enem_dev')])
        run([sys.executable,'-m','python.sincronizar_api_enem','--dataset',str(dataset),
             '--api',str(ROOT/'dados'/'api_enem_dev'),'--out',str(api_dataset)])
        dataset_for_enrichment=api_dataset
    else:
        dataset_for_enrichment=dataset
    run([sys.executable,'-m','python.enriquecer_dataset_questoes','--dataset',str(dataset_for_enrichment),'--out',str(enriched_dataset)])
    embedded_is_valid=False
    if embedded_dataset.exists():
        head=embedded_dataset.read_bytes()[:1000]
        embedded_is_valid=(not head.startswith(b'version https://git-lfs.github.com') and b'embedding' in head.splitlines()[0])
        metadata_path=embedded_dataset.with_name(embedded_dataset.stem+'_metadata.json')
        try:
            metadata=json.loads(metadata_path.read_text(encoding='utf-8'))
            embedded_is_valid &= metadata.get('sourceCsv')==str(enriched_dataset) and metadata.get('sourceMtimeNs')==enriched_dataset.stat().st_mtime_ns
        except (OSError,ValueError): embedded_is_valid=False
    if not args.skip_embeddings and (args.force_embeddings or not embedded_is_valid):
        run([sys.executable,'-m','python.tokenizar_dataset','--csv',str(enriched_dataset),'--out',str(embedded_dataset)])
    elif not args.skip_embeddings:
        print(f'Embeddings já existentes; reutilizando {embedded_dataset}', flush=True)
    if not args.skip_train:
        train_cmd=[sys.executable,'-m','python.treinar_modelo','--csv',str(embedded_dataset),'--out',str(ROOT/'dados'/'modelos')]
        if args.skip_grid_search: train_cmd.append('--skip-grid-search')
        run(train_cmd)
        if not args.skip_ablation:
            run([sys.executable,'-m','python.comparar_embeddings','--csv',str(embedded_dataset),
                 '--out',str(ROOT/'dados'/'modelos'/'estudo_embeddings')])
        if not args.skip_dimension_study:
            run([sys.executable,'-m','python.estudar_dimensoes_embeddings','--csv',str(embedded_dataset),
                 '--out',str(ROOT/'dados'/'modelos'/'estudo_dimensoes')])

if __name__=='__main__': main()
