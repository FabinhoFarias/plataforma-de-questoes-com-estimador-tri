# Guia de execução da pipeline ENEM/TRI

Este guia mostra como clonar o projeto e executar a pipeline local de extração,
montagem do dataset, geração de embeddings MiniLM e treinamento dos modelos.

## 1. Pré-requisitos

- macOS ou Linux;
- Python 3.12;
- Git;
- Git LFS;
- conexão com a internet na primeira instalação e no primeiro download do MiniLM.

No macOS, instale Git LFS com:

```bash
brew install git-lfs
git lfs install
```

## 2. Clonar o projeto e baixar os PDFs

```bash
git clone https://github.com/FabinhoFarias/plataforma-de-questoes-com-estimador-tri.git
cd plataforma-de-questoes-com-estimador-tri
git lfs pull
```

Os PDFs e as tabelas `ITENS_PROVA` ficam em `dados/extraidos/`. Não é necessário
baixar os ZIPs originais do INEP para executar a pipeline disponibilizada no
repositório.

## 3. Criar o ambiente Python

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Executar tudo

Como os pacotes já estão extraídos, use `--skip-reduce`:

```bash
python -m python.main \
  --skip-reduce \
  --include-ambiguous \
  --color AZUL
```

Esse comando executa, nesta ordem:

1. extração do texto dos PDFs azuis;
2. montagem de `dataset_tri.csv` com os parâmetros oficiais `a`, `b` e `c`;
3. geração dos embeddings MiniLM de 384 dimensões;
4. treinamento de Ridge, Extra Trees e Random Forest;
5. gravação das métricas e previsões.

O modelo MiniLM é baixado automaticamente na primeira execução. O aviso de
requisição não autenticada ao Hugging Face é informativo e não impede o uso.

## 5. Arquivos gerados

Depois da execução, os principais arquivos ficam em:

```text
dados/processados/textos/questoes_texto_inep.json
dados/processados/textos/auditoria_extracao_pdf.json
dados/processados/dataset_tri.csv
dados/processados/dataset_tri_revisao.csv
dados/processados/dataset_com_embeddings.csv
dados/processados/dataset_com_embeddings_metadata.json
dados/modelos/metricas.csv
dados/modelos/previsoes_teste.csv
dados/modelos/estimador_tri.joblib
```

`dataset_tri_revisao.csv` contém questões que precisam de conferência, por
exemplo quando há mais de um caderno candidato ou quando a extração possui
figuras e alternativas não textuais.

## 6. Retomar uma execução interrompida

Se `dataset_com_embeddings.csv` já existir, a `main` o reutiliza e não baixa nem
recalcula os embeddings:

```bash
python -m python.main \
  --skip-reduce \
  --skip-extract \
  --include-ambiguous \
  --color AZUL
```

Para recalcular os embeddings:

```bash
python -m python.main \
  --skip-reduce \
  --skip-extract \
  --include-ambiguous \
  --force-embeddings \
  --color AZUL
```

Para executar somente a vetorização:

```bash
python -m python.tokenizar_dataset \
  --csv dados/processados/dataset_tri.csv \
  --out dados/processados/dataset_com_embeddings.csv
```

Para treinar novamente usando os embeddings existentes:

```bash
python -m python.treinar_modelo \
  --csv dados/processados/dataset_com_embeddings.csv \
  --out dados/modelos
```

## 7. Interpretação dos modelos

Os modelos recebem os embeddings dos textos e estimam três saídas:

- `a`: discriminação;
- `b`: dificuldade;
- `c`: acerto ao acaso.

As linhas com `matchQuality=ambiguous` maximizam a quantidade de exemplos, mas
devem ser filtradas para uma avaliação final mais rigorosa:

```python
df = df[df["matchQuality"] == "exact"]
```
