# db-server (PostgreSQL 16)

Contêiner do banco de dados da aplicação. Sobe com `docker compose up --build`
a partir da pasta `projeto/`; na primeira execução cria o schema, importa os
arquivos de `data/` e cria os índices.

## Fontes de dados (dados.gov.br)

| Conjunto | Arquivo | Conteúdo |
|---|---|---|
| Gestão de Pessoas (Executivo Federal) - Aposentados | `APOSENTADOS_MMAAAA[_FULL].csv` | cadastro dos aposentados: nome, CPF mascarado, matrícula, órgão, cargo, tipo e fundamentação da aposentadoria, datas, provento |
| Gestão de Pessoas (Executivo Federal) - Carreiras/Cargos | `CARREIRA_MMAAAA.txt` | servidores ativos: nome, CPF mascarado, carreira, cargo, UF, órgão, mês, remuneração |

Repositório de arquivos: `https://repositorio.dados.gov.br/segrt/`
Dicionário de dados (Aposentados): `https://repositorio.dados.gov.br/segrt/1.20180829-DadosRecursos-Aposentados.pdf`

Os dois arquivos vêm em **latin-1**, separados por `;`, com campos preenchidos
com espaços até o tamanho fixo. O de carreiras tem duas linhas de cabeçalho e
um rodapé com totais. Só a base de ativos possui UF.

## Modelo

```
ufs (sigla PK, nome)
cargos (id PK, nome UNIQUE)
orgaos (id PK, nome UNIQUE, sigla)
servidores (id PK, nome, cpf, matricula, situacao ATIVO|APOSENTADO,
            cargo_id FK, orgao_id FK, uf FK, codigo_carreira, classe, padrao,
            referencia, nivel, tipo_aposentadoria, fundamento_legal,
            diploma_legal, data_inatividade, ocorrencia_ingresso,
            data_ingresso, valor, mes_referencia)
```
