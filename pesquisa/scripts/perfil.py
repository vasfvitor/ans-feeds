"""Perfil de CSVs do FTP da ANS: encoding, separador, colunas, linhas e formato de cada coluna.

Só biblioteca padrão. Rodar com `python3 -I pesquisa/scripts/perfil.py ARQ.csv [...]`.
"""

import collections
import csv
import io
import re
import sys

SEPS = ";,\t|"


def forma(valor):
    """Molde do valor: dígito vira 9, letra vira A, sequências repetidas encurtadas."""
    s = re.sub(r"[0-9]", "9", valor)
    s = re.sub(r"[^\W\d_]", "A", s)
    s = re.sub(r"A{4,}", "A+", s)
    s = re.sub(r"(A\+[ A+]*)+", "A+", s)
    return s[:40]


def detectar_encoding(dados):
    if dados.startswith(b"\xef\xbb\xbf"):
        return "utf-8-sig", "UTF-8 com BOM"
    try:
        dados.decode("utf-8")
        nao_ascii = any(b > 127 for b in dados)
        return "utf-8", "UTF-8" if nao_ascii else "ASCII"
    except UnicodeDecodeError as e:
        return "latin-1", f"não é UTF-8 (byte {e.start}); lido como Latin-1"


def perfil(caminho):
    dados = open(caminho, "rb").read()
    enc, enc_desc = detectar_encoding(dados)
    texto = dados.decode(enc)
    crlf = dados.count(b"\r\n")
    lf = dados.count(b"\n")
    primeira = texto.split("\n", 1)[0]
    sep = max(SEPS, key=primeira.count)
    linhas = list(csv.reader(io.StringIO(texto, newline=""), delimiter=sep))
    while linhas and not any(linhas[-1]):
        linhas.pop()
    cab, corpo = linhas[0], linhas[1:]
    larguras = collections.Counter(len(l) for l in corpo)
    print(f"## {caminho.rsplit('/', 1)[-1]}")
    print(f"bytes={len(dados)} encoding={enc_desc} fim_de_linha={'CRLF' if crlf and crlf == lf else 'LF' if not crlf else f'misto CRLF={crlf} LF={lf}'}")
    print(f"separador={sep!r} aspas_no_cabecalho={'\"' in primeira} colunas={len(cab)} linhas_de_dados={len(corpo)} larguras={dict(larguras)}")
    print(f"linhas_duplicadas={len(corpo) - len(set(map(tuple, corpo)))}")
    for i, nome in enumerate(cab):
        col = [l[i] for l in corpo if len(l) > i]
        vazios = sum(1 for v in col if not v.strip())
        distintos = len(set(col))
        formas = collections.Counter(forma(v) for v in col if v.strip()).most_common(4)
        ex = next((v for v in col if v.strip()), "")
        virgula_decimal = sum(1 for v in col if re.fullmatch(r"-?\d+,\d+", v))
        ponto_decimal = sum(1 for v in col if re.fullmatch(r"-?\d+\.\d+", v))
        dec = f" dec(,)={virgula_decimal} dec(.)={ponto_decimal}" if virgula_decimal or ponto_decimal else ""
        fs = " ".join(f"{f!r}×{n}" for f, n in formas)
        print(f"  {i:2d} {nome!r}: distintos={distintos} vazios={vazios}{dec} formas: {fs} ex={ex[:50]!r}")
    print()


if __name__ == "__main__":
    for c in sys.argv[1:]:
        perfil(c)
