# Aplicação desktop (adicional)

Interface gráfica em **Python + tkinter** que consome a API Flask do backend
por HTTP. Roda fora do Docker, direto na máquina do usuário.

## Executar

```bash
# com a aplicação no ar (docker compose up)
python app_desktop.py
# apontando para outro servidor:
API_URL=http://192.168.0.10:8000 python app_desktop.py
```

Por padrão o `docker compose` publica a porta 8000 só em `127.0.0.1`. Para
usar o app desktop a partir de outra máquina, suba a aplicação com
`API_BIND=0.0.0.0 docker compose up`.

Não precisa instalar nada além do Python 3.10+ (tkinter já vem com ele; no
Linux pode ser necessário `sudo apt install python3-tk`).

## Compilar (executável único)

```bash
pip install pyinstaller
pyinstaller --onefile --windowed --name ServidoresFederais app_desktop.py
```

O executável fica em `dist/ServidoresFederais` (ou `.exe` no Windows).

## Funcionalidades

- Busca por nome exato ou por similaridade (`%NOME%SOBRENOME%` + limite)
- Filtros por cargo, UF, órgão e situação, combináveis
- Lista paginada; registro único abre direto a janela de detalhes
- Duplo clique em uma linha mostra todos os campos do servidor
- Mensagens de erro da API exibidas ao usuário (UF inválida, nome não encontrado, rate limit…)
