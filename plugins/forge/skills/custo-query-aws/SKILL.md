---
name: custo-query-aws
description: Use antes de rodar query Athena/Glue durante investigação — Athena cobra por bytes escaneados, e LIMIT não reduz o scan.
---

# Custo de Query no Athena/Glue

## O modelo de cobrança

Athena cobra por **bytes escaneados**, não por linhas retornadas. `LIMIT`
corta o resultado depois que o scan já aconteceu — ele não reduz custo. Uma
query `SELECT * FROM tabela_gigante LIMIT 10` pode escanear a tabela inteira.

## Antes de rodar, reduza o scan

- **Filtre por partição**: a tabela do data lake (raw/bronze/silver/gold) é
  particionada — inclua a coluna de partição (data, domínio) no `WHERE` antes
  de qualquer outro filtro. Sem partição no filtro, o scan cobre tudo.
- **Evite `SELECT *`**: liste as colunas necessárias. Em formato colunar
  (Parquet/Iceberg via S3 Tables), isso já reduz bytes lidos porque colunas
  não referenciadas nem são tocadas.
- **Prefira projeção**: quando a tabela suportar partition projection ou
  filtros de projeção equivalentes, use-os em vez de escanear metadado para
  descobrir partições.

## Antes de rodar, estime a ordem de grandeza

Pergunte (ou verifique no catálogo/Glue) o tamanho aproximado da tabela e da
partição-alvo antes de disparar a query. Se a estimativa for
desproporcional à pergunta que está sendo respondida — ex.: escanear meses de
dado para confirmar um único evento — avise o usuário antes de rodar, não
depois.

## A armadilha que escala em silêncio

Uma query exploratória rodada uma vez é barata. O mesmo padrão repetido
dezenas de vezes numa investigação (ajustando `WHERE` a cada tentativa, sem
partição, sem reduzir colunas) multiplica o custo sem que nenhuma execução
isolada pareça cara. Trate a primeira query exploratória como modelo a
refinar, não como padrão a repetir.
