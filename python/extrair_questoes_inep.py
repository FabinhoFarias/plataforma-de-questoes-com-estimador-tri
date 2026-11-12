#!/usr/bin/env python3
"""Extrai questões e parâmetros dos ZIPs oficiais do ENEM, sem expandir microdados de participantes.

Dependências: pip install pymupdf
Uso: python scripts/extrair_questoes_inep.py --zip dados/microdados/microdados_enem_2009.zip --year 2009 --color AZUL --out dados/processados/2009
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any

try:
    import fitz  # PyMuPDF
except ImportError:
    fitz = None

AREA_LABELS = {
    "CH": "ciencias-humanas",
    "CN": "ciencias-natureza",
    "LC": "linguagens",
    "MT": "matematica",
}
PARAM_FIELDS = {
    "difficultyA": "NU_PARAM_A",
    "difficultyB": "NU_PARAM_B",
    "guessingC": "NU_PARAM_C",
}
QUESTION_RE = re.compile(r"(?im)^\s*QUEST(?:Ã|A)O\s*(\d{1,3})\b")
ALT_RE = re.compile(r"(?m)^\s*([A-E])\s*[)\].:-]\s*")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zip", required=True, type=Path, help="ZIP principal de microdados do INEP")
    parser.add_argument("--year", required=True, type=int, help="Ano da edição")
    parser.add_argument("--color", default="AZUL", help="Cor/caderno, por exemplo AZUL")
    parser.add_argument("--out", required=True, type=Path, help="Diretório de saída")
    parser.add_argument("--ocr", action="store_true", help="Habilita OCR do PyMuPDF quando não houver texto (requer Tesseract instalado)")
    return parser.parse_args()


def find_member(names: list[str], year: int) -> str:
    candidates = [
        n for n in names
        if "DADOS/" in n.upper().replace("\\", "/")
        and re.fullmatch(rf"ITENS_PROVA_{year}\.CSV", Path(n).name, re.I)
    ]
    if len(candidates) != 1:
        raise FileNotFoundError(
            f"Esperava uma tabela DADOS/ITENS_PROVA_{year}.csv; encontrei: {candidates}"
        )
    return candidates[0]


def read_items(zf: zipfile.ZipFile, year: int, color: str) -> list[dict[str, Any]]:
    member = find_member(zf.namelist(), year)
    with zf.open(member) as stream:
        text = stream.read().decode("latin1")
    reader = csv.DictReader(text.splitlines(), delimiter=";")
    required = {"CO_POSICAO", "SG_AREA", "CO_ITEM", "TX_GABARITO", "TX_COR", "CO_PROVA", *PARAM_FIELDS.values()}
    missing = required - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"{member}: faltam colunas {sorted(missing)}")

    rows = []
    for raw in reader:
        if raw["TX_COR"].strip().upper() != color.upper():
            continue
        if raw.get("IN_ITEM_ABAN", "0").strip() == "1":
            continue
        row: dict[str, Any] = {
            "year": year,
            "position": int(raw["CO_POSICAO"]),
            "disciplineCode": raw["SG_AREA"].strip(),
            "discipline": AREA_LABELS.get(raw["SG_AREA"].strip(), raw["SG_AREA"].strip()),
            "itemCode": raw["CO_ITEM"].strip(),
            "correctAlternative": raw["TX_GABARITO"].strip().upper(),
            "examColor": raw["TX_COR"].strip().upper(),
            "examCode": raw["CO_PROVA"].strip(),
            "skillCode": raw.get("CO_HABILIDADE", "").strip() or None,
            "isAnnulled": raw.get("IN_ITEM_ABAN", "0").strip() == "1",
        }
        for output, source in PARAM_FIELDS.items():
            value = raw[source].strip().replace(",", ".")
            row[output] = float(value) if value else None
        rows.append(row)
    return rows


def extract_pdf_text(pdf_bytes: bytes, use_ocr: bool) -> tuple[str, list[int]]:
    if fitz is None:
        raise RuntimeError("PyMuPDF ausente. Instale com: python -m pip install pymupdf")
    doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    page_texts: list[str] = []
    ocr_pages: list[int] = []
    for page_no, page in enumerate(doc, start=1):
        text = page.get_text("text", sort=True).strip()
        if use_ocr and len(text) < 30:
            try:
                textpage = page.get_textpage_ocr(language="por+eng", dpi=250)
                text = page.get_text("text", textpage=textpage, sort=True).strip()
                ocr_pages.append(page_no)
            except Exception as exc:
                print(f"Aviso: OCR falhou na página {page_no}: {exc}", file=sys.stderr)
        page_texts.append(text)
    return "\n\n".join(page_texts), ocr_pages


def split_questions(text: str) -> dict[int, str]:
    starts = list(QUESTION_RE.finditer(text))
    blocks: dict[int, str] = {}
    for i, match in enumerate(starts):
        start = match.start()
        end = starts[i + 1].start() if i + 1 < len(starts) else len(text)
        number = int(match.group(1))
        block = text[start:end].strip()
        if number in blocks:
            # Duplicata de marcador (ex.: índice no cabeçalho/rodapé): manter bloco mais extenso.
            if len(block) > len(blocks[number]):
                blocks[number] = block
        else:
            blocks[number] = block
    return blocks


def split_alternatives(block: str, correct: str) -> tuple[str, list[dict[str, Any]], str]:
    matches = list(ALT_RE.finditer(block))
    # Só aceitar separação se houver cinco marcadores distintos em ordem A-E.
    letters = [m.group(1) for m in matches]
    valid = len(matches) == 5 and letters == list("ABCDE")
    if not valid:
        return block.strip(), [], "needs_review_alternatives"
    stem = block[:matches[0].start()].strip()
    alternatives = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(block)
        body = block[match.end():end].strip()
        alternatives.append({
            "letter": match.group(1),
            "text": body,
            "file": None,
            "isCorrect": match.group(1) == correct,
        })
    return stem, alternatives, "text_extracted_needs_visual_review"


def discover_proofs(names: list[str], year: int, color: str) -> list[tuple[str, int]]:
    """Encontra PDFs azulados por nomes oficiais que variam entre edições."""
    found = []
    color_norm = color.upper()
    for name in names:
        basename = Path(name).name
        if not basename.lower().endswith(".pdf"):
            continue
        upper = basename.upper()
        if not any(token in upper for token in ("PROVA", "CADERNO")):
            continue
        if color_norm not in upper:
            continue
        year_match = re.search(r"(?:ENEM_?|ENEM)(19\d{2}|20\d{2})", upper)
        if year_match and int(year_match.group(1)) != year:
            continue
        day_match = re.search(r"DIA[_ ]?(\d)|(?:SAB|SÁB)", upper)
        if day_match:
            day = int(day_match.group(1)) if day_match.group(1) else 1
        elif re.search(r"DOM", upper):
            day = 2
        else:
            # Alguns arquivos usam P1/P2 ou Cad_01/Cad_07.
            p_match = re.search(r"P([12])_CAD", upper)
            c_match = re.search(r"CAD(?:ERNO)?[_ ]?(\d+)", upper)
            if p_match:
                day = int(p_match.group(1))
            elif c_match:
                code = int(c_match.group(1))
                day = 1 if code <= 4 else 2
            else:
                continue
        # Ignorar ledor/adaptados por padrão: layouts distintos exigem configuração própria.
        if "LEDOR" in upper or "AMPLIADA" in upper:
            continue
        found.append((name, day))
    return sorted(set(found), key=lambda x: (x[1], x[0]))


def main() -> int:
    args = parse_args()
    if not args.zip.is_file():
        raise FileNotFoundError(args.zip)
    args.out.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(args.zip) as zf:
        names = zf.namelist()
        item_rows = read_items(zf, args.year, args.color)
        proofs = discover_proofs(names, args.year, args.color)
        if not proofs:
            raise FileNotFoundError(f"PDF de prova {args.year} cor {args.color} não encontrado")
        print(f"Itens oficiais {args.year}/{args.color}: {len(item_rows)}")
        print("PDFs:", [Path(p).name for p, _ in proofs])

        records = []
        page_audit = []
        for pdf_member, day in proofs:
            text, ocr_pages = extract_pdf_text(zf.read(pdf_member), args.ocr)
            blocks = split_questions(text)
            page_audit.append({"pdf": Path(pdf_member).name, "day": day,
                               "chars": len(text), "questionMarkers": len(blocks), "ocrPages": ocr_pages})
            # Itens identificados pela cor oficial e pela faixa de posições do dia.
            # Os limites tradicionais (46..135 no dia 1; 136..180 no dia 2) aplicam-se ao ENEM 2009;
            # demais anos usam posições 1..90 em cada dia nos layouts disponíveis.
            if args.year == 2009:
                day_rows = [r for r in item_rows if
                            (day == 1 and 46 <= r["position"] <= 135) or
                            (day == 2 and 136 <= r["position"] <= 180)]
            else:
                max_pos = max((r["position"] for r in item_rows), default=180)
                if max_pos > 180:
                    day_rows = [r for r in item_rows if (day == 1 and r["position"] <= max_pos // 2) or
                                (day == 2 and r["position"] > max_pos // 2)]
                else:
                    day_rows = [r for r in item_rows if (day == 1 and r["position"] <= 90) or
                                (day == 2 and r["position"] > 90)]
            for row in day_rows:
                pos = row["position"]
                # A API-like index é numeração local estimada dentro da área; a posição INEP é chave oficial.
                # Para a edição 2009, faixas de posição por área constam no layout; questão local é 1..45.
                area_start = {"CH": 46, "CN": 91, "LC": 136, "MT": 136}.get(row["disciplineCode"]) if args.year == 2009 else None
                qnum = pos - area_start + 1 if area_start is not None else pos
                block = blocks.get(qnum, "")
                stem, alternatives, status = split_alternatives(block, row["correctAlternative"]) if block else ("", [], "needs_review_no_question_marker")
                row_out = {
                    "title": f"Questão {qnum} - ENEM {args.year}",
                    "index": qnum,
                    "discipline": row["discipline"],
                    "year": args.year,
                    "context": stem,
                    "files": [],
                    "correctAlternative": row["correctAlternative"],
                    "alternativesIntroduction": None,
                    "alternatives": alternatives,
                    **row,
                    "day": day,
                    "sourcePdf": Path(pdf_member).name,
                    "extractionStatus": status if block else "needs_review_no_question_marker",
                    "ocrUsed": bool(args.ocr),
                }
                records.append(row_out)

    # Um registro por caderno/posição, preservando linhas do INEP como rótulos.
    json_path = args.out / f"enem_{args.year}_{args.color.lower()}_questoes.json"
    json_path.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = args.out / f"enem_{args.year}_{args.color.lower()}_questoes.csv"
    columns = ["year", "day", "examColor", "examCode", "disciplineCode", "discipline", "index", "position",
               "itemCode", "correctAlternative", "difficultyA", "difficultyB", "guessingC", "context", "extractionStatus", "sourcePdf"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns, extrasaction="ignore")
        writer.writeheader(); writer.writerows(records)
    audit_path = args.out / f"enem_{args.year}_{args.color.lower()}_auditoria.json"
    audit_path.write_text(json.dumps({"year": args.year, "color": args.color.upper(),
                                      "records": len(records), "statusCounts": dict(Counter(r["extractionStatus"] for r in records)),
                                      "pdfs": page_audit}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"JSON: {json_path}\nCSV: {csv_path}\nAuditoria: {audit_path}")
    print("Status:", dict(Counter(r["extractionStatus"] for r in records)))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERRO: {exc}", file=sys.stderr)
        raise
