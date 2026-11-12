# Pipeline Python local

Na raiz do projeto, instale as dependências e execute:

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
python -m python.main --color AZUL
```

O comando percorre `dados/microdados`, reduz os ZIPs para tabelas de itens/documentação/PDFs da cor escolhida, extrai texto em JSON, junta o conteúdo aos parâmetros oficiais A/B/C, gera embeddings MiniLM e treina regressores. O embedding é um vetor de 384 números por questão, não a sequência de IDs internos do tokenizador. Use Python 3.12 para evitar dependências sem wheels para versões recentes do Python. A primeira instalação baixa PyTorch, Sentence Transformers e o modelo MiniLM; reserve espaço em disco. ZIPs são preservados por padrão. Para removê-los depois de uma extração validada, passe `--delete-zips`.

Opções para retomar etapas:

```bash
python -m python.main --skip-reduce --color AZUL
python -m python.main --skip-reduce --skip-extract --skip-train --color AZUL
```

Como os arquivos já reduzidos e o JSON de texto existem localmente, o comando
para montar, vetorizar e treinar usando esses arquivos é:

```bash
python -m python.main --skip-reduce --skip-extract --color AZUL
```

O montador só aprova pareamentos que consegue validar por edição, área, posição
e código de prova único. As demais linhas vão para `dataset_tri_revisao.csv`.
Com os arquivos presentes hoje, o dataset aprovado cobre 2012–2014; versões de
cadernos e variantes de idioma de outros anos continuam na revisão até haver
um mapeamento inequívoco de `CO_PROVA` para o PDF correspondente. Assim o treino
é parcial e não representa todas as edições disponíveis.

Para executar só a vetorização MiniLM sobre um CSV já montado:

```bash
python -m python.tokenizar_dataset \
  --csv dados/processados/dataset_tri.csv \
  --out dados/processados/dataset_com_embeddings.csv
```

O CSV com embeddings mantém os metadados e parâmetros A/B/C e inclui a coluna
`embedding` com um vetor JSON de 384 dimensões por linha. O treinamento lê esse
arquivo e grava métricas, previsões e o modelo em `dados/modelos/`.

O comando orquestra as etapas, mas o dataset ainda exige validação do pareamento por edição/caderno/área/posição. Revise `dataset_tri_revisao.csv` e a auditoria dos PDFs antes de usar as métricas como resultado final. Edições sem PDF de prova não geram texto, mesmo que tenham tabela A/B/C.

## Embeddings MiniLM local

O encoder local usa o modelo e a implementação de `EmbeddingEngine` copiados de
`python/mac_embeddings/engine.py`, sem servidor FastAPI nem túnel Cloudflare.
O treino grava `dataset_com_embeddings.csv`, com um vetor float32 na coluna
`embedding` por questão, além das métricas, previsões e estimador serializado.
O modelo MiniLM é baixado do Hugging Face na primeira execução.
