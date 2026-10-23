"""PDA-055 (reajuste de agrupamento, contratos coletivos com menos de 30 vidas): ciclos, chave, junção com o
CADOP, valores extremos e o dicionário (.ods).

Só biblioteca padrão. Rodar com
`python3 -I pesquisa/scripts/pda055.py PDA055.csv DICIONARIO.ods SNAPSHOT_CADOP`.
"""

import collections
import csv
import re
import sys
import zipfile


def num(v):
    return float(v.replace(",", ".")) if v else None


def dicionario(ods):
    with zipfile.ZipFile(ods) as z:
        xml = z.read("content.xml").decode("utf-8")
    for linha in re.findall(r"<table:table-row[^>]*>(.*?)</table:table-row>", xml, re.S):
        celulas = [re.sub(r"<[^>]+>", "", c).strip() for c in re.findall(r"<table:table-cell[^>]*>(.*?)</table:table-cell>", linha, re.S)]
        celulas = [c for c in celulas if c]
        if celulas:
            print("  |", " | ".join(celulas))


def main():
    arq, ods, cadop = sys.argv[1:4]
    with open(arq, encoding="utf-8", newline="") as f:
        linhas = list(csv.DictReader(f, delimiter=";"))
    print("### dicionário")
    dicionario(ods)

    print("### ciclos")
    por_ciclo = collections.defaultdict(list)
    for r in linhas:
        por_ciclo[r["CICLO"]].append(r)
    for ciclo, rs in sorted(por_ciclo.items()):
        tipos = collections.Counter(r["TP_AGRUPAMENTO"] for r in rs)
        unicos = [num(r["PCT_UNICO"]) for r in rs if r["PCT_UNICO"]]
        unicos.sort()
        mediana = unicos[len(unicos) // 2] if unicos else None
        print(f"  {ciclo}: {len(rs)} linhas, {len({r['REGISTRO_OPERADORA'] for r in rs})} operadoras, {dict(tipos)},"
              f" PCT_UNICO mediana {mediana} min {unicos[0] if unicos else None} max {unicos[-1] if unicos else None},"
              f" benef {sum(int(r['QT_BENEF']) for r in rs)}")

    print("### chave")
    chave = collections.Counter((r["REGISTRO_OPERADORA"], r["CICLO"], r["TP_AGRUPAMENTO"]) for r in linhas)
    print("  (registro, ciclo, tipo) repetidas:", sum(1 for v in chave.values() if v > 1))
    chave2 = collections.Counter((r["REGISTRO_OPERADORA"], r["CICLO"]) for r in linhas)
    print("  (registro, ciclo) repetidas:", sum(1 for v in chave2.values() if v > 1),
          "ex:", [k for k, v in chave2.items() if v > 1][:3])
    prefixo = sum(1 for r in linhas if not r["RAZAO_SOCIAL"].startswith(r["REGISTRO_OPERADORA"] + " - "))
    print("  RAZAO_SOCIAL sem o prefixo 'registro - ':", prefixo)

    print("### PCT_UNICO vazio × segmentados")
    vazio = [r for r in linhas if not r["PCT_UNICO"]]
    print("  vazios:", len(vazio), "tipos:", dict(collections.Counter(r["TP_AGRUPAMENTO"] for r in vazio)),
          "com algum segmentado:", sum(1 for r in vazio if r["PCT_AMBULATORIAL"] or r["PCT_INT_SEM_OBSTET"] or r["PCT_INT_COM_OBSTET"]))
    ambos = [r for r in linhas if r["PCT_UNICO"] and (r["PCT_AMBULATORIAL"] or r["PCT_INT_SEM_OBSTET"] or r["PCT_INT_COM_OBSTET"])]
    print("  único e segmentado na mesma linha:", len(ambos))
    for r in vazio[:3]:
        print("  ", {k: v for k, v in r.items() if k != "RAZAO_SOCIAL"})

    print("### extremos")
    for r in sorted(linhas, key=lambda r: num(r["PCT_UNICO"]) or 0)[:3] + sorted(linhas, key=lambda r: -(num(r["PCT_UNICO"]) or 0))[:8]:
        print("  ", r["REGISTRO_OPERADORA"], r["CICLO"], r["TP_AGRUPAMENTO"], r["PCT_UNICO"], r["QT_CONTRATOS"], r["QT_BENEF"])

    print("### junção com o CADOP")
    regs = {}
    for nome in ("Relatorio_cadop.csv", "Relatorio_cadop_canceladas.csv"):
        with open(f"{cadop}/{nome}", encoding="utf-8", newline="") as f:
            for r in csv.DictReader(f, delimiter=";"):
                regs[r["REGISTRO_OPERADORA"]] = nome
    todos = {r["REGISTRO_OPERADORA"] for r in linhas}
    print("  operadoras:", len(todos), "fora do CADOP:", sorted(todos - regs.keys()),
          "ativas:", sum(1 for x in todos if regs.get(x) == "Relatorio_cadop.csv"))
    ultimo = max(por_ciclo)
    ult = {r["REGISTRO_OPERADORA"] for r in por_ciclo[ultimo]}
    print(f"  ciclo {ultimo}: {len(ult)} operadoras, ativas no CADOP: {sum(1 for x in ult if regs.get(x) == 'Relatorio_cadop.csv')}")


main()
