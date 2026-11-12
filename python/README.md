# Pipeline Python local

Na raiz do projeto, instale as dependências e execute:

```bash
python3 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m python.main --color AZUL
```

O comando percorre `dados/microdados`, reduz os ZIPs para tabelas de itens/documentação/PDFs da cor escolhida, extrai texto em JSON, junta o conteúdo aos parâmetros oficiais A/B/C e treina regressores com embeddings MiniLM. A primeira instalação baixa PyTorch, Sentence Transformers e o modelo MiniLM; reserve espaço em disco e use Python 3.11 ou 3.12. ZIPs são preservados por padrão. Para removê-los depois de uma extração validada, passe `--delete-zips`.

Opções para retomar etapas:

```bash
python -m python.main --skip-reduce --color AZUL
python -m python.main --skip-reduce --skip-extract --skip-train --color AZUL
```

O comando orquestra as etapas, mas o dataset ainda exige validação do pareamento por edição/caderno/área/posição. Revise `dataset_tri_revisao.csv` e a auditoria dos PDFs antes de usar as métricas como resultado final. Edições sem PDF de prova não geram texto, mesmo que tenham tabela A/B/C.

## Embeddings MiniLM local

O encoder local usa o modelo e a implementação de `EmbeddingEngine` copiados de
`python/mac_embeddings/engine.py`, sem servidor FastAPI nem túnel Cloudflare.
O treino grava `dataset_com_embeddings.csv`, com um vetor float32 na coluna
`embedding` por questão, além das métricas, previsões e estimador serializado.
O modelo MiniLM é baixado do Hugging Face na primeira execução.
