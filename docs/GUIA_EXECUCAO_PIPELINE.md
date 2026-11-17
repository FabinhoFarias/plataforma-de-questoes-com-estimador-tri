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

Os pacotes já extraídos são detectados automaticamente quando os ZIPs não estão disponíveis:

```bash
python -m python.main \
  --include-ambiguous \
  --color AZUL
```

Para refazer a redução, coloque os arquivos `microdados_enem_*.zip` em
`dados/microdados` antes de executar o comando.

Para resolver `CO_PROVA` por gabarito oficial, use:

```bash
python -m python.main --color AZUL --include-ambiguous --download-gabaritos
```

Esse modo tenta baixar os gabaritos azuis do índice oficial do INEP para
`dados/gabaritos/<ano>/`. Se o servidor estiver indisponível, baixe os PDFs
manualmente e coloque-os nessas pastas. O nome deve identificar o dia (`D1`
ou `D2`), o caderno azul (`CD1`, `CD7` ou `AZUL`) e a aplicação (`impresso`/
`P1`, `reaplicacao`/`PPL`/`P2` ou `digital`). O arquivo
`dados/processados/mapa_co_prova.json` registra código, gabarito e taxa de
concordância. Só são promovidos a `matchQuality=exact` os mapeamentos com
pelo menos 25 respostas comparáveis por área, concordância mínima de 95% e
vantagem de 15 pontos percentuais sobre outro grupo de itens.

Esse comando executa, nesta ordem:

1. extração do texto dos PDFs azuis;
2. montagem de `dataset_tri.csv` com os parâmetros oficiais `a`, `b` e `c`;
3. download incremental das questões ENEM.DEV de 2009 a 2023 e sincronização por ano e número da questão da prova azul regular, com conferência de área e gabarito;
4. cruzamento do texto sincronizado com `QuestoesEnem` e seus metadados;
5. geração dos embeddings MiniLM de 384 dimensões;
6. treinamento dos regressores e gravação das métricas.

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

O cruzamento com `dados/QuestoesEnem` usa similaridade textual dentro da área da questão. Metadados com pareamento incerto não entram no treino. O arquivo `dados/processados/dataset_tri_enriquecido.csv` registra `metadata_match_status` e `metadata_match_score` para auditoria. O treino usa apenas `matchQuality=exact`, remove itens/textos repetidos e separa treino, validação e teste por texto. A escolha do estimador é feita separadamente para `a`, `b` e `c` com base na validação; `dados/modelos/metricas.csv` contém o teste e `dados/modelos/metricas_validacao.csv` contém a validação. A `main` reaproveita vetores existentes quando o texto não mudou.
Na divisão padrão, 80% dos itens ficam no treino, 10% na validação e 10% no teste, aproximadamente.
O treinamento executa uma busca em grade com validação cruzada agrupada em 3 partes
apenas no conjunto de treino. As combinações e seus erros ficam em
`dados/modelos/grid_search_resultados.csv`; os parâmetros escolhidos ficam em
`dados/modelos/melhores_hiperparametros.json`. Depois, a validação escolhe o
regressor de cada parâmetro TRI e o teste mede o resultado final. Para uma
execução rápida com os valores padrão, acrescente `--skip-grid-search` ao comando
`python -m python.treinar_modelo`.

No fluxo atual, os embeddings e o treino usam **somente** questões cujo texto revisado
da pasta `QuestoesEnem` foi confirmado contra a extração do PDF. A confirmação
exige área e aplicação compatíveis, resposta correta igual, as cinco
alternativas concordantes. O caminho principal exige similaridade do enunciado
de pelo menos 0,88. Para PDFs cujo enunciado saiu corrompido, um segundo caminho
exige similaridade alta nas cinco alternativas, texto suficiente nelas e alguma
concordância do enunciado. Candidatos próximos são marcados como ambíguos.
O arquivo `dados/processados/dataset_tri_enriquecido_pares_confirmados.csv`
mostra os dois textos lado a lado para auditoria manual. Os demais pares ficam
em `dataset_tri_enriquecido_auditoria.csv` e não entram no treino. O texto do PDF
continua em `pdf_text` para rastreabilidade; `text` passa a ser o texto revisado.
Esses critérios elevam a precisão esperada, mas não garantem 100% de acerto sem
conferência humana dos pares confirmados.

`dataset_tri_revisao.csv` contém questões que precisam de conferência, por
exemplo quando há mais de um caderno candidato ou quando a extração possui
figuras e alternativas não textuais.

Os arquivos da API ficam em `dados/api_enem_dev/<ano>.json`; o pareamento e sua
auditoria ficam em `dataset_tri_api.csv` e `dataset_tri_api_auditoria.csv`.
O campo `api_match` registra `wrong_application`, `area_mismatch`,
`answer_mismatch`, `missing_api` ou `incomplete_api` quando a API não pode
fornecer texto confiável. Questões PPL podem usar o texto confirmado da pasta
`QuestoesEnem`. A montagem mantém itens com extração de alternativas incompleta
para que a etapa da API ainda possa recuperá-los.
Use `--skip-api-download` quando os JSON da API já estiverem em `dados/api_enem_dev`
e você quiser apenas sincronizá-los novamente. Use `--skip-api` apenas quando
quiser trabalhar sem a fonte ENEM.DEV.

## 6. Retomar uma execução interrompida

Se `dataset_com_embeddings.csv` já existir, a `main` reaproveita os vetores dos
textos que não mudaram e calcula apenas os novos:

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

## 8. Questões externas e avaliação acadêmica

Depois de treinar, estime uma questão externa pelo formato de
[`docs/exemplo_questao_externa.json`](exemplo_questao_externa.json):

```bash
python -m python.prever_questoes --input docs/exemplo_questao_externa.json --out dados/processados/previsao_exemplo.json
```

Campos obrigatórios: `area` (`CH`, `CN`, `LC` ou `MT`) e `enunciado`.
`alternativas` deve conter cinco textos quando fornecida. `assunto`,
`competencia`, `habilidade` e `dificuldade` são opcionais. A saída separa o
método escolhido na validação dos modelos textuais experimentais. Em particular,
se o baseline por área vencer para `b`, duas questões da mesma área receberão
a mesma previsão principal; consulte também `faixa_dificuldade_textual_experimental`
para a distinção exploratória pelo texto. O intervalo empírico deriva de erros de validação
no ENEM e **não tem cobertura verificada para simulados externos**.

Para um teste acadêmico temporal, por exemplo treino anterior a 2022,
validação em 2022 e teste em 2023:

```bash
python -m python.treinar_modelo --csv dados/processados/dataset_com_embeddings.csv \
  --out dados/modelos/academico_2023 --validation-year 2022 --test-year 2023
```

Após coletar respostas reais de questões externas, crie um CSV longo com
colunas `id,correta` (`correta` = 0 ou 1) e rode:

```bash
python -m python.avaliar_questoes_externas \
  --previsoes dados/processados/previsoes_externas.json \
  --respostas dados/respostas_externas.csv \
  --out dados/modelos/avaliacao_externa.json
```

São necessários pelo menos dez itens e 30 respostas por item (ajustável por
`--min-respostas`). Essa avaliação mede a associação entre `b` previsto e
proporção de acertos; **proporção de acertos não equivale a parâmetro TRI**.
Se houver parâmetros `a,b,c` calibrados e ligados à mesma escala, passe também
`--parametros dados/parametros_externos.csv` para calcular MAE/RMSE/R².

## 9. Análise exploratória

Depois de gerar `dataset_com_embeddings.csv`, execute:

```bash
python -m python.analisar_dataset
```

O script seleciona os mesmos itens `exact` únicos usados no treino e cria
`dados/analise_exploratoria/relatorio.md`, `resumo.json` e seis gráficos PNG em
`dados/analise_exploratoria/imagens/`. O relatório inclui distribuições de
`a`, `b` e `c`, correlações Pearson e Spearman, comparação entre áreas,
cobertura dos metadados e relação entre o rótulo de dificuldade e `b`.

## 10. Estudo com e sem embeddings

O treino normal pela `python.main` também executa a comparação dos mesmos
modelos, itens e divisões com e sem os embeddings MiniLM. Resultados em
`dados/modelos/estudo_embeddings/metricas.csv`, `comparacao_teste.csv` e
`relatorio.md`. A importância por permutação de grupos de atributos, medida
na validação, fica em `importancias_permutacao.csv`. Para executar isoladamente:

```bash
python -m python.comparar_embeddings
```

Para reservar anos inteiros, use `--validation-year 2022 --test-year 2023`.
Se quiser pular esta etapa na `main`, use `--skip-ablation`.

O pipeline completo também estuda automaticamente a quantidade de componentes
PCA dos embeddings, mantendo os mesmos itens e a mesma divisão. Para repetir
somente esse estudo, execute:

```bash
python -m python.estudar_dimensoes_embeddings
```

O estudo usa 6, 125, 245 e 364 dimensões e salva relatório, gráfico e métricas
em `dados/modelos/estudo_dimensoes/`.
Use `--skip-dimension-study` para pular esta etapa na `python.main`.
