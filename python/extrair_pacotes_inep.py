#!/usr/bin/env python3
"""Extrai somente arquivos úteis dos ZIPs de microdados do ENEM numa pasta.

Mantém os ZIPs originais intactos e não expande MICRODADOS_ENEM_<ano>.csv.
Para cada ano, copia tabela ITENS_PROVA, dicionário/leia-me e PDFs de provas/gabaritos.
Também gera um relatório com a estrutura encontrada para documentar variações entre edições.
"""

from __future__ import annotations
import argparse
import csv
import json
import re
import zipfile
from pathlib import Path, PurePosixPath

USEFUL_DOC = re.compile(r"(dicion|leia.?me|read.?me)", re.I)
PROOF_DOC = re.compile(r"(prova|caderno|gabarito|gab[_ -])", re.I)
ITEM_TABLE = re.compile(r"^ITENS_PROVA_(\d{4})\.CSV$", re.I)


def safe_basename(member: str) -> str:
    # ZIPs carregam diretórios em português e, por vezes, nomes repetidos.
    return PurePosixPath(member.replace("\\", "/")).name


def classify(member: str, year: int) -> str | None:
    name = safe_basename(member)
    upper = name.upper()
    m = ITEM_TABLE.fullmatch(name)
    if m and int(m.group(1)) == year:
        return "itens"
    if name.lower().endswith((".xlsx", ".ods", ".pdf", ".doc", ".docx", ".txt")) and USEFUL_DOC.search(name):
        if name.startswith("~$") or ".history" in name.lower():
            return None
        return "documentacao"
    if name.lower().endswith(".pdf") and (PROOF_DOC.search(name) or re.search(r"(?:^|_)CAD(?:_|\d)", upper)):
        # Exclui relatórios e manuais grandes que mencionam prova no título.
        if re.search(r"(PROVA|CADERNO|GABARITO|GAB[_ -]|(?:^|_)CAD(?:_|\d))", upper):
            return "prova_gabarito"
    return None


def canonical_color(filename: str) -> str | None:
    upper = Path(filename).name.upper()
    for alias, canonical in (("AMARELO", "AMARELO"), ("AMARELA", "AMARELO"),
                             ("AZUL", "AZUL"), ("BRANCO", "BRANCO"),
                             ("BRANCA", "BRANCO"), ("ROSA", "ROSA"), ("CINZA", "CINZA")):
        if alias in upper:
            return canonical
    return None


def infer_day(filename: str) -> int | None:
    upper = Path(filename).name.upper()
    m = re.search(r"DIA[_ ]?(\d)", upper)
    if m:
        return int(m.group(1))
    if "SAB" in upper or "SÁB" in upper:
        return 1
    if "DOM" in upper:
        return 2
    m = re.search(r"P([12])_CAD", upper)
    if m:
        return int(m.group(1))
    m = re.search(r"CAD(?:ERNO)?[_ ]?(\d+)", upper)
    if m:
        return 1 if int(m.group(1)) <= 4 else 2
    return None


def inspect_zip(zip_path: Path, output_root: Path, colors: set[str] | None = None) -> dict:
    year_match = re.search(r"(19\d{2}|20\d{2})", zip_path.name)
    if not year_match:
        raise ValueError(f"Ano não identificado no nome: {zip_path.name}")
    year = int(year_match.group(1))
    target = output_root / str(year)
    groups: dict[str, list[dict]] = {"itens": [], "documentacao": [], "prova_gabarito": []}
    all_members = []
    with zipfile.ZipFile(zip_path) as zf:
        for info in zf.infolist():
            if info.is_dir():
                continue
            category = classify(info.filename, year)
            if category == "prova_gabarito" and colors:
                basename_upper = safe_basename(info.filename).upper()
                is_answer_key = "GAB" in basename_upper or "GABARITO" in basename_upper
                found_color = canonical_color(info.filename)
                if not is_answer_key and found_color not in colors:
                    category = None
            all_members.append({"member": info.filename, "bytes": info.file_size, "category": category})
            if not category:
                continue
            basename = safe_basename(info.filename)
            # Prefixa nomes repetidos com diretório normalizado para não sobrescrever.
            dest = target / category / basename
            dest.parent.mkdir(parents=True, exist_ok=True)
            if dest.exists() and dest.stat().st_size == info.file_size:
                pass
            else:
                with zf.open(info) as src, open(dest, "wb") as dst:
                    while True:
                        chunk = src.read(1024 * 1024)
                        if not chunk:
                            break
                        dst.write(chunk)
            groups[category].append({"member": info.filename, "extracted": str(dest), "bytes": info.file_size})

    # Checagem superficial da tabela de itens e das cores/cadernos por área.
    table_reports = []
    available_colors = {}
    pdf_by_color = {}
    extracted_members = {entry["member"] for entry in groups["prova_gabarito"]}
    for member in (m["member"] for m in all_members):
        basename = Path(member).name
        upper = basename.upper()
        if not basename.lower().endswith(".pdf") or not re.search(r"(PROVA|CADERNO|(?:^|_)CAD(?:_|\d))", upper):
            continue
        if "GAB" in upper or "GABARITO" in upper:
            continue
        color = canonical_color(basename)
        if color:
            size = next((m["bytes"] for m in all_members if m["member"] == member), 0)
            pdf_by_color.setdefault(color, []).append({"filename": basename, "member": member,
                "day": infer_day(basename), "bytes": size, "extracted": member in extracted_members})
    for entry in groups["itens"]:
        path = Path(entry["extracted"])
        with path.open(encoding="latin1", newline="") as f:
            reader = csv.DictReader(f, delimiter=";")
            fields = reader.fieldnames or []
            count = sum(1 for _ in reader)
        color_col = next((c for c in ("TX_COR", "SG_COR", "CO_COR") if c in fields), None)
        if color_col:
            with path.open(encoding="latin1", newline="") as f:
                reader = csv.DictReader(f, delimiter=";")
                for row in reader:
                    color = row.get(color_col, "").strip().upper()
                    area = row.get("SG_AREA", "").strip().upper()
                    if color:
                        available_colors.setdefault(color, {})
                        available_colors[color][area] = available_colors[color].get(area, 0) + 1
        table_reports.append({"file": str(path), "columns": fields, "rows": count,
                              "has_abc": all(x in fields for x in ("NU_PARAM_A", "NU_PARAM_B", "NU_PARAM_C")),
                              "has_keys": all(x in fields for x in ("CO_POSICAO", "SG_AREA", "CO_ITEM", color_col or "TX_COR", "CO_PROVA")),
                              "color_column": color_col})

    color_inventory = {}
    for color, areas in available_colors.items():
        normalized = {"AMARELA":"AMARELO", "BRANCA":"BRANCO"}.get(color, color)
        color_inventory.setdefault(normalized, {"table_areas": {}, "pdf_present": False, "proof_pdfs": []})
        color_inventory[normalized]["table_areas"].update(areas)
    for color in color_inventory:
        color_inventory[color]["proof_pdfs"] = pdf_by_color.get(color, [])
        color_inventory[color]["pdf_present"] = bool(color_inventory[color]["proof_pdfs"])
    report = {"year": year, "zip": str(zip_path), "zip_bytes": zip_path.stat().st_size,
              "members": all_members, "selected": groups, "item_tables": table_reports,
              "colors": color_inventory,
              "unselected_member_count": sum(1 for m in all_members if m["category"] is None)}
    (target / "estrutura_pacote.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=Path("dados/microdados"), help="Pasta com ZIPs originais")
    parser.add_argument("--output", type=Path, default=Path("dados/extraidos"), help="Pasta para arquivos selecionados")
    parser.add_argument("--color", action="append", help="Extrai apenas esta cor de caderno; pode repetir (ex.: AZUL)")
    parser.add_argument("--delete-zips", action="store_true", help="Apaga cada ZIP original após validar extração de ITENS_PROVA e PDFs da cor selecionada")
    args = parser.parse_args()
    colors = {canonical_color(c) or c.upper() for c in args.color} if args.color else None
    zips = sorted(args.input.glob("microdados_enem_*.zip"))
    if not zips:
        raise FileNotFoundError(f"Nenhum ZIP microdados_enem_*.zip em {args.input}")
    reports = []
    for path in zips:
        print(f"Inspecionando {path.name} ({path.stat().st_size / 1024**2:.1f} MiB)")
        report = inspect_zip(path, args.output, colors)
        reports.append(report)
        for table in report["item_tables"]:
            print(f"  tabela={Path(table['file']).name}, linhas={table['rows']}, A/B/C={table['has_abc']}, chaves={table['has_keys']}")
        print("  extraídos:", {k: len(v) for k, v in report["selected"].items()})
        valid = bool(report["item_tables"] and report["item_tables"][0]["has_abc"] and report["item_tables"][0]["has_keys"])
        requested = colors or set()
        if requested:
            valid = valid and all(report["colors"].get(c, {}).get("pdf_present", False) for c in requested)
        if args.delete_zips and valid:
            path.unlink()
            print(f"  ZIP original removido após validação: {path}")
        elif args.delete_zips:
            print("  ZIP mantido: extração necessária incompleta ou sem PDF da cor pedida")
        print("  cadernos por cor:", {
            color: {"areas": sorted(info["table_areas"]),
                    "pdfs": [p["filename"] for p in info["proof_pdfs"]],
                    "extraídos": [p["filename"] for p in info["proof_pdfs"] if p["extracted"]]}
            for color, info in report["colors"].items()
        })
    args.output.mkdir(parents=True, exist_ok=True)
    summary = [{"year": r["year"], "zip": r["zip"], "selected": {k: len(v) for k,v in r["selected"].items()},
                "item_tables": r["item_tables"], "colors": r["colors"]} for r in reports]
    (args.output / "relatorio_estrutura.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Concluído: {len(reports)} ZIP(s). Relatório: {args.output / 'relatorio_estrutura.json'}")

if __name__ == "__main__":
    main()
