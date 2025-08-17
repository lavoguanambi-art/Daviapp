# APP DAVI — v8.1 (Importar Extrato + Dashboard com Gráficos)

- Importar Extrato (CSV/PDF)
- Balde Imprevistos automático
- Datas DD/MM/YY, moeda BRL
- Dashboard com gráficos (Barras, Pizza, Linha)

## Rodar
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python seed.py
streamlit run app.py --server.port 8504 --server.headless true
```
