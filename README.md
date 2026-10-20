# Trabalho de Sistemas para Internet II — 3º Bimestre

Aplicação full stack para consulta de servidores ativos e aposentados do
Poder Executivo Federal (dados.gov.br), com **PostgreSQL**, **Flask +
Gunicorn** e **frontend web**, orquestrados com **Docker Compose**.

Todo o código fica na pasta [`projeto/`](projeto/). Para rodar:

```bash
cd projeto
docker compose up --build
```

- Interface web: http://localhost:8080
- API: http://localhost:8000/api

Documentação completa (endpoints, erros, testes, estrutura): [`projeto/README.md`](projeto/README.md).

## Equipe

| Integrante | Papel |
|---|---|
| Thiago Neves | líder técnico · backend/API Flask + Gunicorn · testes de carga · relatório |
| Caio Almeida de Souza | banco de dados PostgreSQL · importação e tratamento dos dados · índices · infra |
| Caio Neves Ferreira | frontend web · integração com a API · aplicação desktop |

Gestão das tarefas no Jira (projeto SCRUM); cada commit referencia a tarefa correspondente.
