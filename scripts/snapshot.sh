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
# RAIZ/FALHAS.tsv: as fontes que falharam nesta execução (dia, nome, motivo), reescrito a cada vez
# e vazio quando nada falha; o build publica isso para o portal dizer qual fonte não atualizou.
lista_falhas=$tmp/falhas.tsv
: > "$lista_falhas"
falhou() {
  echo "FALHA: $1 ($2)" >&2
  printf '%s\t%s\t%s\n' "$dia" "$1" "$2" >> "$lista_falhas"
}
# a fonte que não foi atualizada nesta execução fica com a linha anterior do estado
manter_anterior() {
  awk -F'\t' -v n="$1" '$1 == n' "$estado" >> "$novo_estado"
}

# nome<TAB>url<TAB>guardar (sim: copia para o snapshot; não: só registra Last-Modified e sha256)
fontes=$(cat <<EOF
Relatorio_cadop.csv	$ftp/operadoras_de_plano_de_saude_ativas/Relatorio_cadop.csv	sim
Relatorio_cadop_canceladas.csv	$ftp/operadoras_de_plano_de_saude_canceladas/Relatorio_cadop_canceladas.csv	sim
pda-023-igr.csv	$ftp/IGR/IGR_versao_2023/pda-023-igr.csv	sim
pda-048-taxa_de_resolutividade.csv	$ftp/taxa_de_resolutividade/pda-048-taxa_de_resolutividade.csv	sim
pda-040-regimes_especiais_direcao_tecnica.csv	$ftp/regimes_especiais_direcao_tecnica/pda-040-regimes_especiais_direcao_tecnica.csv	sim
pda-056-classificacao_prudencial.csv	$ftp/classificacao_prudencial-056/pda-056-classificacao_prudencial.csv	sim
monit_garantia_atendimento.csv	$ftp/monitoramento_garantia_atendimento/monit_garantia_atendimento.csv	sim
penalidades_aplicadas_a_operadoras.csv	$ftp/penalidades_aplicadas_a_operadoras/penalidades_aplicadas_a_operadoras.csv	não
portabilidade-especial.html	$govbr/assuntos/contratacao-e-troca-de-plano/operadoras-em-fase-de-portabilidade-especial-e-portabilidade-extraordinaria	sim
EOF
)

# PDFs das listas RN 623: os nomes mudam a cada trimestre, então vêm dos links da página.
lista=$govbr/assuntos/informacoes-e-avaliacoes-de-operadoras/lista-excelencia-e-reducao-das-reclamacoes-das-operadoras
if curl -sS --fail --max-time 120 -A "$ua" -o "$tmp/lista.html" "$lista"; then
  pdfs=$(sed -n 's/.*href="\(https:\/\/www\.gov\.br\/ans\/[^"]*Lista[^"]*\.pdf\)".*/\1/p' "$tmp/lista.html" | sort -u)
  # uma página em manutenção ou redesenhada responde 200 sem nenhum link: não é "nada novo"
  [ -z "$pdfs" ] && falhou "listas RN 623" "nenhum PDF na página"
  while IFS= read -r url; do
    [ -n "$url" ] && fontes+=$'\n'"${url##*/}"$'\t'"$url"$'\t'sim
  done <<< "$pdfs"
else
  falhou "listas RN 623" "página fora do ar"
fi

# Arquivos cujo nome muda com o tempo: pegos no diretório, o mais recente em ordem de nome.
#   mais_recente <url do diretório> <padrão ERE do nome> <rótulo para FALHAS.tsv>
mais_recente() {
  local dir=$1 padrao=$2 rotulo=$3 arq
  if ! curl -sS --fail --max-time 120 -A "$ua" -o "$tmp/dir.html" "$dir/"; then
    falhou "$rotulo" "diretório fora do ar"
    return
  fi
  arq=$(sed -nE "s/.*href=\"($padrao)\".*/\1/p" "$tmp/dir.html" | sort | tail -1)
  if [ -z "$arq" ]; then
    falhou "$rotulo" "nenhum arquivo no diretório"
    return
  fi
  fontes+=$'\n'"$arq"$'\t'"$dir/$arq"$'\t'sim
}
# o índice de ressarcimento sai todo mês (AAAAMM_...)
mais_recente "$ftp/ressarcimento_ao_SUS_indice_efetivo_pagamento" \
  '[0-9]{6}_Indice_de_Efetivo_Pagamento\.csv' "índice de ressarcimento"
# um HC por ano: em janeiro o do ano novo ainda não existe, e o do ano anterior segue sendo o coletado
mais_recente "$ftp/hc_ressarcimento_sus" 'HC_[0-9]{4}\.csv' "HC do ressarcimento"
# o nome do IDSS traz a faixa de anos e cresce um ano por vez (…2016_2025.csv, …2016_2026.csv)
mais_recente "$ftp/historico_idss-020" 'pda-020-historico-idss-[0-9]{4}_[0-9]{4}\.csv' "histórico do IDSS"

touch "$estado"
novo_estado=$tmp/estado.tsv
: > "$novo_estado"
guardados=()

while IFS=$'\t' read -r nome url guardar; do
  [ -z "$nome" ] && continue
  lm_ant='' sha_ant='' bytes_ant='' snap_ant=''
  IFS=$'\t' read -r lm_ant sha_ant bytes_ant snap_ant < <(awk -F'\t' -v n="$nome" '$1 == n {print $3 "\t" $4 "\t" $5 "\t" $6}' "$estado") || true
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
      manter_anterior "$nome"
      echo "igual (304)  $nome"
      continue ;;
    200) ;;
    *)
      falhou "$nome" "HTTP $code"
      manter_anterior "$nome"
      continue ;;
  esac
  sha=$(sha256sum "$tmp/corpo" | cut -d' ' -f1)
  bytes=$(stat -c %s "$tmp/corpo")
  # menos da metade do tamanho anterior: arquivo cortado, página de erro ou de manutenção com 200;
  # fica a versão anterior, e a execução falha
  if [[ "${bytes_ant:-}" =~ ^[0-9]+$ ]] && [ "$bytes_ant" -gt 0 ] && [ $((bytes * 2)) -lt "$bytes_ant" ]; then
    falhou "$nome" "$bytes bytes contra $bytes_ant na versão anterior"
    manter_anterior "$nome"
    continue
  fi
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
cp "$lista_falhas" "$raiz/FALHAS.tsv"
falhas=$(wc -l < "$lista_falhas")
echo "guardados em $dest: ${#guardados[@]}; falhas: $falhas"
[ "$falhas" -eq 0 ]
