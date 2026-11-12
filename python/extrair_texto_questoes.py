#!/usr/bin/env python3
"""Extrai blocos de texto dos cadernos PDF reduzidos do INEP para JSON.

Não associa nem inventa parâmetros: a junção com A/B/C é feita no script
montar_dataset_tri.py usando a tabela ITENS_PROVA oficial.
"""
from __future__ import annotations
import argparse, json, re, sys, zipfile
from pathlib import Path

try:
    import fitz
except ImportError:
    fitz = None

COLOR_ALIASES = {"AZUL":"AZUL", "AMARELO":"AMARELO", "AMARELA":"AMARELO", "BRANCO":"BRANCO", "BRANCA":"BRANCO", "ROSA":"ROSA", "CINZA":"CINZA"}
Q_RE = re.compile(r"(?im)^\s*(?:QUEST(?:Ã|A)O\s*)?(\d{1,3})\s*[.)-]\s*(?=\S)")
EXPLICIT_Q_RE = re.compile(r"(?im)^\s*QUEST(?:Ã|A)O\s*(\d{1,3})\b")
ALT_RE = re.compile(r"(?m)^[ \t]*([A-E])(?:[ \t]*[)\].:-][ \t]*|[ \t]+)(?=\S)")
ALT_ONLY_RE = re.compile(r"(?m)^[ \t]*([A-E])[ \t]*$")


def normalize_color(text: str) -> str | None:
    token = re.sub(r"[^A-Z]", "", text.upper())
    return COLOR_ALIASES.get(token)


def pdf_identity(member: str, year: int):
    name = Path(member).name
    up = name.upper()
    # INEP changed naming over time: older files say PROVA/CADERNO, while
    # newer files commonly use ENEM_<year>_P1_CAD_<n>_... .
    if not name.lower().endswith('.pdf') or not re.search(r'(PROVA|CADERNO|(?:^|_)CAD(?:_|\d))', up):
        return None
    if re.search(r'(GABARITO|GAB[_ -])', up):
        return None
    # Ignore special/adapted copies in the first pass; layout may not match the item table.
    if any(x in up for x in ('LEDOR','AMPLIADA','2_APLICAC','2ª_APLIC','2A_APLIC')):
        return None
    color = next((c for c in COLOR_ALIASES if re.search(rf'(?<![A-Z]){re.escape(c)}(?![A-Z])', up)), None)
    if color is None:
        # filenames concatenate color and day token, e.g. Caderno1_Azul_Sab.pdf
        for alias, canonical in COLOR_ALIASES.items():
            if alias in up:
                color = canonical; break
    if color is None:
        return None
    if re.search(r'(DIA[_ ]?1|_SAB|SAB_)', up): day = 1
    elif re.search(r'(DIA[_ ]?2|_DOM|DOM_)', up): day = 2
    else:
        m = re.search(r'P([12])_CAD', up)
        c = re.search(r'CAD(?:ERNO)?[_ ]?(\d+)', up)
        if m: day = int(m.group(1))
        elif c: day = 1 if int(c.group(1)) <= 4 else 2
        else: return None
    return {"year":year,"color":COLOR_ALIASES[color],"day":day,"pdf":name,"member":member}


def extract_pdf(pdf_bytes: bytes, identity: dict, use_ocr: bool):
    if fitz is None:
        raise RuntimeError('Instale dependências: python -m pip install -r requirements.txt')
    doc = fitz.open(stream=pdf_bytes, filetype='pdf')
    pages=[]
    for page_no,page in enumerate(doc,1):
        text=page_text_in_reading_order(page)
        ocr_used=False
        if use_ocr and len(text)<30:
            try:
                tp=page.get_textpage_ocr(language='por+eng',dpi=300)
                text=page_text_in_reading_order(page,tp); ocr_used=True
            except Exception as e:
                print(f'OCR indisponível na página {page_no}: {e}',file=sys.stderr)
        pages.append({"page":page_no,"text":text,"ocrUsed":ocr_used})
    full='\n\n'.join(p['text'] for p in pages)
    # Prefer explicit QUESTÃO labels; fallback to numbered item headings only if none exist.
    matches=list(EXPLICIT_Q_RE.finditer(full))
    marker_type='explicit_question'
    if not matches:
        matches=list(Q_RE.finditer(full)); marker_type='numbered_heading_heuristic'
    blocks=[]
    for i,m in enumerate(matches):
        end=matches[i+1].start() if i+1<len(matches) else len(full)
        block=full[m.start():end].strip()
        number=int(m.group(1))
        alternatives=[]
        block,am=find_alternative_markers(block)
        if len(am)==5:
            for j,a in enumerate(am):
                stop=am[j+1].start() if j+1<len(am) else len(block)
                alternatives.append({"letter":a.group(1),"text":block[a.end():stop].strip()})
            stem=block[:am[0].start()].strip()
            alt_status='five_markers_detected' if all(a['text'] for a in alternatives) else 'needs_review'
        else:
            stem=block; alt_status='needs_review'
        blocks.append({**identity,"index":number,"title":f"Questão {number} - ENEM {identity['year']}",
                       "discipline":None,"context":stem,"alternativesIntroduction":None,
                       "alternatives":alternatives,"sourcePages":[],"markerType":marker_type,
                       "alternativeStatus":alt_status,"textLength":len(block)})
    # Map each extracted question to page(s) for audit; page ranges approximate text offsets.
    offset=0; spans=[]
    for page in pages:
        spans.append((offset,offset+len(page['text']),page['page'])); offset+=len(page['text'])+2
    for block,m in zip(blocks,matches):
        start=m.start(); end=start+block['textLength']
        block['sourcePages']=sorted({p for a,b,p in spans if a<end and b>start})
    audit={**identity,"pageCount":len(pages),"nonemptyPages":sum(bool(p['text']) for p in pages),
           "ocrPages":[p['page'] for p in pages if p['ocrUsed']],"markerType":marker_type,
           "questionCount":len(blocks),"pages":pages}
    return blocks,audit


def page_text_in_reading_order(page, textpage=None):
    """Read each PDF column top-to-bottom, then move to the next column.

    PyMuPDF's page-wide sort=True sorts by y before x. On ENEM's two-column
    layouts that interleaves unrelated questions and creates large gaps.
    """
    raw_blocks = page.get_text('blocks', textpage=textpage, sort=False)
    midpoint = page.rect.width / 2
    columns = [[], []]
    for block in raw_blocks:
        x0, y0, x1, y1, raw_text, *_ = block
        value = raw_text.strip()
        if not value:
            continue
        if re.fullmatch(r'\*?[0-9]{5,}[A-Z0-9]{1,}\*?', value.replace(' ', '')):
            continue
        # Drop recurring running headers and page footers, keeping question text.
        if y1 < 38:
            continue
        if y0 > page.rect.height - 80 and re.search(
            r'(?i)(?:ENEM\s*20\d\d|CADERNO\s*\d.*AZUL|(?:AZUL|AMARELO)[–-]|\b[LCN]H?\s*[•–-]\s*\d+.*DIA)',
            value,
        ):
            continue
        column = 0 if (x0 + x1) / 2 < midpoint else 1
        # Normalize spacing within each text block; retain block boundaries so
        # answer options and paragraphs remain detectable.
        value = re.sub(r'[ \t\u00a0]+', ' ', value)
        value = re.sub(r' *\n *', '\n', value).strip()
        # Recent INEP PDFs repeat this text as a diagonal watermark; it is not
        # part of the question and can otherwise create enormous noisy blocks.
        value = re.sub(r'(?i)(?:\bENEM\s*20\d{2}\b\s*){3,}', ' ', value).strip()
        columns[column].append((y0, x0, value))
    ordered = [entry[2] for col in columns for entry in sorted(col, key=lambda item: (item[0], item[1]))]
    return '\n'.join(ordered).strip()


def find_alternative_markers(block: str):
    """Find a complete A-E sequence, ignoring duplicated PDF glyph labels."""
    normalized = re.sub(
        r'(?m)^[ \t]*([A-E])[ \t]*\n[ \t]*\1[ \t]*(?=\S)',
        r'\1 ',
        block,
    )
    candidates = list(ALT_RE.finditer(normalized))
    candidates.extend(ALT_ONLY_RE.finditer(normalized))
    candidates.sort(key=lambda match: match.start())
    for start in range(max(0, len(candidates) - 4)):
        group = candidates[start:start + 5]
        if [match.group(1) for match in group] == list('ABCDE'):
            return normalized, group
    return normalized, []


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input',type=Path,default=Path('dados/extraidos'),help='Raiz com <ano>/prova_gabarito PDFs extraídos')
    ap.add_argument('--output',type=Path,default=Path('dados/processados/textos'),help='Saída JSON')
    ap.add_argument('--year',type=int,action='append',help='Ano (pode repetir); padrão: todos encontrados')
    ap.add_argument('--color',action='append',help='Cor (pode repetir); padrão: cores encontradas')
    ap.add_argument('--ocr',action='store_true',help='OCR em páginas sem texto; requer Tesseract e por+eng')
    args=ap.parse_args(); args.output.mkdir(parents=True,exist_ok=True)
    years=args.year or sorted(int(p.name) for p in args.input.iterdir() if p.is_dir() and p.name.isdigit())
    selected={normalize_color(c) for c in args.color} if args.color else None
    all_records=[]; audits=[]
    for year in years:
        pdf_dir=args.input/str(year)/'prova_gabarito'
        if not pdf_dir.exists(): print(f'Sem pasta {pdf_dir}',file=sys.stderr); continue
        pdfs=[]
        for p in sorted(pdf_dir.glob('*.pdf')):
            identity=pdf_identity(p.name,year)
            if identity and (selected is None or identity['color'] in selected): pdfs.append((p,identity))
        for path,identity in pdfs:
            print(f"Lendo {year} {identity['color']} dia {identity['day']}: {path.name}")
            blocks,audit=extract_pdf(path.read_bytes(),identity,args.ocr)
            for b in blocks:
                # identify source file and page; only assign area later by official item table.
                b['sourceFile']=str(path)
            all_records.extend(blocks); audits.append(audit)
    out=args.output/'questoes_texto_inep.json'
    out.write_text(json.dumps(all_records,ensure_ascii=False,indent=2),encoding='utf-8')
    (args.output/'auditoria_extracao_pdf.json').write_text(json.dumps(audits,ensure_ascii=False,indent=2),encoding='utf-8')
    print(f'{len(all_records)} blocos extraídos -> {out}')
    print(f'Auditoria -> {args.output}/auditoria_extracao_pdf.json')

if __name__=='__main__': main()
