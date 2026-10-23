#!/usr/bin/env bash
# Snapshot do que a ANS não guarda em histórico: baixa só o que mudou desde o último snapshot e
# guarda em RAIZ/AAAA-MM-DD/, com SHA256SUMS e FONTES.tsv. A memória entre execuções é
# RAIZ/ESTADO.tsv (Last-Modified e sha256 da última versão vista de cada arquivo), porque o git não
# preserva mtime. Só curl, sha256sum, awk e sed. Não faz commit.
#
# Uso: scripts/snapshot.sh [RAIZ] [DIA]
#   RAIZ padrão snapshots; DIA padrão a data de hoje em Brasília.
set -euo pipefail

raiz=${1:-snapshots}
dia=${2:-$(TZ=America/Sao_Paulo date +%F)}
dest=$raiz/$dia
estado=$raiz/ESTADO.tsv
tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
ua="ans-feeds/0 (+https://github.com/vasfvitor/ans-feeds)"
ftp=https://dadosabertos.ans.gov.br/FTP/PDA
govbr=https://www.gov.br/ans/pt-br
falhas=0

# nome<TAB>url<TAB>guardar (sim: copia para o snapshot; não: só registra Last-Modified e sha256)
ano=$(TZ=America/Sao_Paulo date +%Y)
fontes=$(cat <<EOF
Relatorio_cadop.csv	$ftp/operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv	sim
Relatorio_cadop_canceladas.csv	$ftp/operadoras_de_plano_de_saude_canceladas/Relatorio_cadop_canceladas.csv	sim
pda-023-igr.csv	$ftp/IGR/IGR_versao_2023/pda-023-igr.csv	sim
pda-048-taxa_de_resolutividade.csv	$ftp/taxa_de_resolutividade/pda-048-taxa_de_resolutividade.csv	sim
pda-040-regimes_especiais_direcao_tecnica.csv	$ftp/regimes_especiais_direcao_tecnica/pda-040-regimes_especiais_direcao_tecnica.csv	sim
pda-056-classificacao_prudencial.csv	$ftp/classificacao_prudencial-056/pda-056-classificacao_prudencial.csv	sim
monit_garantia_atendimento.csv	$ftp/monitoramento_garantia_atendimento/monit_garantia_atendimento.csv	sim
HC_$ano.csv	$ftp/hc_ressarcimento_sus/HC_$ano.csv	sim
pda-020-historico-idss-2016_2025.csv	$ftp/historico_idss-020/pda-020-historico-idss-2016_2025.csv	sim
penalidades_aplicadas_a_operadoras.csv	$ftp/penalidades_aplicadas_a_operadoras/penalidades_aplicadas_a_operadoras.csv	não
portabilidade-especial.html	$govbr/assuntos/contratacao-e-troca-de-plano/operadoras-em-fase-de-portabilidade-especial-e-portabilidade-extraordinaria	sim
EOF
)

# PDFs das listas RN 623: os nomes mudam a cada trimestre, então vêm dos links da página.
lista=$govbr/assuntos/informacoes-e-avaliacoes-de-operadoras/lista-excelencia-e-reducao-das-reclamacoes-das-operadoras
if curl -sS --fail --max-time 120 -A "$ua" -o "$tmp/lista.html" "$lista"; then
  pdfs=$(sed -n 's/.*href="\(https:\/\/www\.gov\.br\/ans\/[^"]*Lista[^"]*\.pdf\)".*/\1/p' "$tmp/lista.html" | sort -u)
  while IFS= read -r url; do
    [ -n "$url" ] && fontes+=$'\n'"${url##*/}"$'\t'"$url"$'\t'sim
  done <<< "$pdfs"
else
  echo "FALHA: página das listas RN 623" >&2
  falhas=$((falhas + 1))
fi

# Índice de ressarcimento ao SUS: um arquivo por mês (AAAAMM_...), só o mais recente.
ress=$ftp/ressarcimento_ao_SUS_indice_efetivo_pagamento
if curl -sS --fail --max-time 120 -A "$ua" -o "$tmp/ress.html" "$ress/"; then
  arq=$(sed -n 's/.*href="\([0-9]\{6\}_Indice_de_Efetivo_Pagamento\.csv\)".*/\1/p' "$tmp/ress.html" | sort | tail -1)
  [ -n "$arq" ] && fontes+=$'\n'"$arq"$'\t'"$ress/$arq"$'\t'sim
else
  echo "FALHA: diretório do índice de ressarcimento" >&2
  falhas=$((falhas + 1))
fi

touch "$estado"
novo_estado=$tmp/estado.tsv
: > "$novo_estado"
guardados=()

while IFS=$'\t' read -r nome url guardar; do
  [ -z "$nome" ] && continue
  lm_ant='' sha_ant='' snap_ant=''
  IFS=$'\t' read -r lm_ant sha_ant snap_ant < <(awk -F'\t' -v n="$nome" '$1 == n {print $3 "\t" $4 "\t" $6}' "$estado") || true
  cond=()
  [ -n "${lm_ant:-}" ] && [ "$lm_ant" != "-" ] && cond=(-H "If-Modified-Since: $lm_ant")
  if ! code=$(curl -sS --max-time 600 -A "$ua" "${cond[@]}" -D "$tmp/h" -o "$tmp/corpo" -w '%{http_code}' "$url"); then
    code=000
  fi
  # O proxy pode antepor a resposta do CONNECT: vale o último bloco de cabeçalhos.
  lm=$(tr -d '\r' < "$tmp/h" | awk '{l = tolower($0)} l ~ /^http\// {lm = "-"} l ~ /^last-modified:/ {sub(/^[^:]*: */, ""); lm = $0} END {print (lm == "" ? "-" : lm)}')
  agora=$(date -u +%FT%TZ)
  case $code in
    304)
      awk -F'\t' -v n="$nome" '$1 == n' "$estado" >> "$novo_estado"
      echo "igual (304)  $nome"
      continue ;;
    200) ;;
    *)
      echo "FALHA ($code) $nome" >&2
      falhas=$((falhas + 1))
      awk -F'\t' -v n="$nome" '$1 == n' "$estado" >> "$novo_estado"
      continue ;;
  esac
  sha=$(sha256sum "$tmp/corpo" | cut -d' ' -f1)
  bytes=$(stat -c %s "$tmp/corpo")
  if [ "$sha" = "${sha_ant:-}" ]; then
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$nome" "$url" "$lm" "$sha" "$bytes" "$snap_ant" "$guardar" >> "$novo_estado"
    echo "igual (sha)  $nome"
    continue
  fi
  snap=-
  if [ "$guardar" = sim ]; then
    mkdir -p "$dest"
    mv "$tmp/corpo" "$dest/$nome"
    [ "$lm" != "-" ] && touch -d "$lm" "$dest/$nome"
    printf '%s\t%s\t%s\t%s\n' "$nome" "$url" "$lm" "$agora" >> "$dest/FONTES.tsv"
    snap=$dia
    guardados+=("$nome")
    echo "NOVO         $nome ($bytes bytes, Last-Modified $lm)"
  else
    echo "MUDOU        $nome ($bytes bytes, Last-Modified $lm; não guardado)"
  fi
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$nome" "$url" "$lm" "$sha" "$bytes" "$snap" "$guardar" >> "$novo_estado"
done <<< "$fontes"

# Entradas do estado que saíram da lista de fontes (HC do ano anterior, PDF retirado) ficam.
awk -F'\t' 'NR == FNR {visto[$1]; next} !($1 in visto)' "$novo_estado" "$estado" >> "$novo_estado"
sort -t$'\t' -k1,1 "$novo_estado" > "$estado"

if [ ${#guardados[@]} -gt 0 ]; then
  (cd "$dest" && sha256sum -- $(ls | sed '/^SHA256SUMS$/d;/^FONTES.tsv$/d;/^cadop_diff.txt$/d') > SHA256SUMS)
fi
echo "guardados em $dest: ${#guardados[@]}; falhas: $falhas"
[ "$falhas" -eq 0 ]
