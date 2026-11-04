# Documento de Requisitos — Estimador de Parâmetros TRI

## 1. Visão geral

O sistema será uma plataforma web para consulta e estimativa de parâmetros da
Teoria de Resposta ao Item (TRI) aplicados a questões do ENEM e a questões
inéditas ou provenientes de outras bancas.

O produto terá dois fluxos principais:

1. **Consulta de questão ENEM calibrada:** o usuário informa uma questão
   existente no conjunto de dados do ENEM e o sistema retorna o enunciado, as
   alternativas, os metadados e os parâmetros TRI previamente obtidos a partir
   dos microdados e da calibração de referência.
2. **Estimativa de questão inédita:** o usuário fornece uma questão que não
   possui calibração prévia e o sistema extrai suas características, aplica o
   modelo de aprendizado de máquina e retorna uma estimativa dos três parâmetros
   TRI: discriminação (`a`), dificuldade (`b`) e acerto ao acaso (`c`).

A plataforma deve deixar explícito se um valor é **calibrado** (observado e
armazenado para uma questão ENEM) ou **estimado** (produzido pelo modelo para
uma questão sem parâmetros de referência).

## 2. Contexto e problema

A TRI estima a proficiência do participante (`θ`) a partir de seu desempenho em
itens calibrados. Para isso, cada item precisa de três parâmetros:

- **`a` — discriminação:** capacidade do item de diferenciar participantes com
  diferentes níveis de proficiência;
- **`b` — dificuldade:** nível de proficiência associado à dificuldade do item;
- **`c` — acerto ao acaso:** probabilidade de acerto por chute.

Questões de plataformas externas, como SAS e Poliedro, normalmente não
disponibilizam esses parâmetros. Sem eles, não é possível incorporá-las
diretamente a uma escala TRI com a mesma confiabilidade dos itens calibrados.
O projeto propõe aprender a relação entre características observáveis de uma
questão e os parâmetros `a`, `b` e `c`, reduzindo a necessidade de uma nova
aplicação em larga escala para cada questão.

## 3. Objetivos

- Disponibilizar uma base pesquisável de questões ENEM com seus parâmetros TRI
  de referência.
- Permitir a inspeção dos dados usados na calibração e da origem de cada
  parâmetro.
- Estimar `a`, `b` e `c` para uma questão inédita a partir do texto, das
  alternativas, da estrutura e dos metadados informados.
- Exibir a incerteza, a qualidade e as limitações da estimativa, evitando que
  uma previsão seja apresentada como parâmetro oficial.
- Produzir uma solução reprodutível, auditável e extensível para novas bancas
  e conjuntos de questões.

## 4. Escopo

### 4.1 Incluído

- Importação e versionamento dos microdados do ENEM necessários à calibração.
- Cadastro ou ingestão das questões, alternativas, gabaritos e metadados.
- Armazenamento dos parâmetros TRI calibrados e de sua versão de origem.
- Busca e visualização de uma questão ENEM pelo ano, prova, área, número,
  código ou outro identificador disponível.
- Formulário para submissão de questão inédita.
- Extração de características textuais, estruturais, pedagógicas e estatísticas
  quando disponíveis.
- Aplicação de modelos supervisionados para regressão de `a`, `b` e `c`.
- Exibição dos resultados, métricas de qualidade e avisos de validade.
- Registro das entradas, versão do modelo e resultados para auditoria.

### 4.2 Fora do escopo inicial

- Substituir a calibração TRI oficial do INEP.
- Garantir que uma previsão de ML tenha validade oficial ou psicométrica sem
  validação empírica.
- Calcular a proficiência individual (`θ`) de um participante como produto
  principal da primeira versão.
- Editar ou republicar microdados protegidos ou alterar documentos oficiais.
- Treinar automaticamente em produção sem um processo explícito de validação e
  publicação do modelo.

## 5. Usuários e permissões

### 5.1 Usuário consultante

- Pesquisa questões ENEM calibradas.
- Visualiza parâmetros, metadados, origem e avisos.
- Submete uma questão inédita para estimativa.
- Consulta o resultado da própria estimativa.

### 5.2 Administrador ou responsável técnico

- Importa e valida microdados.
- Publica versões da base calibrada e dos modelos.
- Acompanha métricas, erros e registros de processamento.
- Corrige metadados e desativa versões inválidas.

O controle de acesso deve impedir que usuários comuns alterem parâmetros
calibrados ou versões publicadas.

## 6. Requisitos funcionais

### RF-01 — Ingestão dos microdados do ENEM

O sistema deve permitir importar microdados identificando, no mínimo, ano,
edição, área, caderno, item, gabarito, respostas dos participantes e a versão
da fonte.

Durante a importação, o sistema deve:

- validar o formato e os campos obrigatórios;
- detectar registros duplicados e inconsistentes;
- informar quantidades importadas, rejeitadas e motivos de rejeição;
- manter a versão e a data da importação;
- permitir reprocessamento idempotente da mesma fonte.

### RF-02 — Calibração e armazenamento de referência

O sistema deve armazenar os parâmetros calibrados (`a`, `b`, `c`) por item ENEM,
associados à metodologia, à amostra, à versão dos microdados e à data da
calibração.

Deve ser possível distinguir:

- parâmetro de referência/calibrado;
- parâmetro estimado pelo modelo;
- parâmetro ausente ou não validado.

Valores inválidos para o modelo TRI adotado devem ser rejeitados ou marcados
explicitamente para revisão, nunca convertidos silenciosamente em zero.

### RF-03 — Consulta de questão ENEM

O usuário deve poder informar um identificador de questão ou combinar filtros
como ano, área do conhecimento, prova, caderno e número do item.

Quando houver correspondência, o sistema deve retornar:

- enunciado completo;
- alternativas na ordem original;
- gabarito, quando permitido pela fonte;
- ano, área, competência/habilidade e demais metadados disponíveis;
- parâmetros `a`, `b` e `c` calibrados;
- fonte, versão da calibração e data de atualização;
- indicação de que os valores são de referência, e não previsões do modelo.

Quando não houver correspondência, o sistema deve informar claramente que o
item não foi localizado e oferecer a entrada no fluxo de questão inédita, sem
inventar dados.

### RF-04 — Entrada de questão inédita

O formulário deve aceitar:

- enunciado;
- alternativas, com quantidade configurável e mínimo de duas;
- identificação da alternativa correta, quando conhecida;
- área do conhecimento, disciplina, competência ou habilidade;
- tipo de comando e demais metadados pedagógicos;
- imagens, tabelas ou fórmulas, quando suportados;
- origem/banca opcional, sem tratar a origem como calibração.

O sistema deve validar campos obrigatórios, tamanho, quantidade e unicidade das
alternativas e apresentar erros de validação ao usuário antes do processamento.

### RF-05 — Extração de características

Para a questão inédita, o sistema deve gerar um vetor de características
versionado, contendo, quando aplicável:

- **textuais:** comprimento do enunciado, complexidade lexical, quantidade de
  alternativas e presença de negação;
- **estruturais:** tipo de comando, formato das alternativas e presença de
  imagens ou fórmulas;
- **pedagógicas:** área, disciplina, competência e habilidade;
- **estatísticas:** padrões de desempenho e informações de resposta, somente
  quando existirem e forem informadas de forma válida.

O sistema deve registrar as características utilizadas ou informar quais foram
desconsideradas. A ausência de uma característica opcional não deve resultar
em uma previsão silenciosamente apresentada como equivalente à previsão
completa.

### RF-06 — Estimativa dos três parâmetros

O sistema deve aplicar uma versão publicada do modelo de regressão
supervisionada e retornar:

- `â` (discriminação estimada);
- `b̂` (dificuldade estimada);
- `ĉ` (acerto ao acaso estimado);
- versão do modelo e das features;
- intervalo, escore de confiança ou indicador de incerteza, quando suportado;
- aviso de que os valores são estimativas.

O modelo deve aprender o mapeamento
`características observáveis → (a, b, c)` a partir de itens previamente
calibrados. A implementação pode comparar regressão linear múltipla, Random
Forest, Gradient Boosting/XGBoost e MLP, em saída multioutput ou em regressões
independentes, selecionando a versão com melhor desempenho validado.

As previsões devem respeitar as restrições do modelo TRI adotado, especialmente
os limites físicos ou psicométricos definidos para `c`. Se uma previsão sair
dos limites, o sistema deve registrar o evento e aplicar uma regra de
validação documentada, sem ocultar o valor original ou o motivo do ajuste.

### RF-07 — Resultado e interpretação

O resultado deve apresentar os três parâmetros em tabela e linguagem acessível,
incluindo a interpretação de cada um. Deve informar que `a`, `b` e `c` não
constituem, isoladamente, uma nota do aluno.

Para uma questão inédita, a tela deve exibir também:

- características usadas;
- alertas de dados ausentes;
- domínio de treinamento e similaridade, se disponível;
- limitações de generalização;
- opção de exportar ou consultar o identificador do processamento.

### RF-08 — Avaliação dos modelos

O processo de treinamento e validação deve calcular separadamente para `a`, `b`
e `c`:

- **MAE:** erro absoluto médio;
- **RMSE:** erro quadrático médio, com maior penalização para erros grandes;
- **R²:** proporção da variância de referência explicada pelo modelo.

O sistema deve registrar partições de treino, validação e teste, quantidade de
itens, distribuição por área/banca e a versão do conjunto de dados. A publicação
de um modelo deve exigir métricas disponíveis e identificação do conjunto de
teste.

### RF-09 — Auditoria e rastreabilidade

Cada consulta ou estimativa deve possuir identificador e registrar, conforme a
política de privacidade:

- entrada e metadados da questão;
- versão dos dados, features e modelo;
- parâmetros retornados;
- avisos e falhas de validação;
- data, duração e status do processamento.

## 7. Requisitos não funcionais

- **RNF-01 — Usabilidade:** os dois fluxos devem estar separados visualmente,
  com rótulos “calibrado” e “estimado” sempre visíveis.
- **RNF-02 — Desempenho:** uma consulta de item já calibrado deve responder sem
  executar treinamento; a estimativa deve informar progresso e não bloquear
  indefinidamente a interface.
- **RNF-03 — Reprodutibilidade:** a mesma entrada, usando as mesmas versões,
  deve produzir o mesmo resultado ou declarar a fonte de aleatoriedade.
- **RNF-04 — Segurança:** validar e limitar arquivos e textos recebidos,
  proteger funções administrativas e evitar exposição de dados individuais dos
  microdados.
- **RNF-05 — Observabilidade:** falhas de ingestão, extração, inferência e
  validação devem ser registradas com mensagem acionável.
- **RNF-06 — Acessibilidade:** interface navegável por teclado, contraste
  adequado, rótulos associados aos campos e mensagens de erro compreensíveis.
- **RNF-07 — Extensibilidade:** permitir adicionar novas bancas, áreas, versões
  de dados e modelos sem alterar o contrato dos fluxos existentes.

## 8. Arquitetura conceitual e fluxo

### 8.1 Consulta de item ENEM

`identificador/filtros → busca na base ENEM → item + metadados → parâmetros
calibrados + fonte → apresentação`

Esse caminho não deve chamar o modelo de ML. Seu objetivo é recuperar o valor
de referência associado ao item.

### 8.2 Estimativa de item inédito

`enunciado + alternativas + metadados → validação → extração de features →
modelo publicado → (â, b̂, ĉ) → validação dos limites → resultado e auditoria`

O pipeline experimental do PDF é composto por coleta de dados,
pré-processamento, treino/validação/teste e regressão/avaliação. A plataforma
deve manter treinamento e publicação do modelo separados da inferência feita
pelo usuário.

## 9. Modelo de dados mínimo

- **Questão:** identificador, origem, ano, área, enunciado, alternativas,
  gabarito e metadados pedagógicos.
- **Resposta:** questão, participante anonimizado ou agregado, resposta e
  demais campos necessários à calibração.
- **Calibração:** questão, `a`, `b`, `c`, método, amostra, versão da fonte e
  data.
- **FeatureSet:** questão/processamento, vetor de features, versão do extrator
  e campos ausentes.
- **Modelo:** versão, algoritmo, conjunto de treino, hiperparâmetros, métricas
  por parâmetro, status de publicação e data.
- **Estimativa:** entrada, modelo, `â`, `b̂`, `ĉ`, incerteza, avisos e status.

## 10. Critérios de aceitação

1. Ao consultar um item ENEM existente, a plataforma exibe a questão completa,
   seus metadados e os três parâmetros calibrados, identificando a fonte.
2. Ao consultar um item inexistente, a plataforma não cria valores artificiais e
   informa que não há calibração disponível.
3. Ao enviar uma questão inédita válida, a plataforma retorna exatamente três
   resultados nomeados `a`, `b` e `c`, além da versão do modelo e do aviso de
   estimativa.
4. Uma entrada inválida é rejeitada com mensagem específica e não gera
   estimativa parcial.
5. O resultado de uma estimativa permite reproduzir qual versão de features e
   modelo foi utilizada.
6. O relatório do modelo apresenta MAE, RMSE e R² individualmente para os três
   parâmetros.
7. Uma falha de processamento é visível ao usuário e registrada para
   diagnóstico, sem retorno de sucesso vazio.

## 11. Limitações, riscos e premissas

- Os parâmetros de referência dependem da qualidade da calibração TRI, da
  amostra de respondentes e de possíveis vieses do conjunto de dados.
- Dataset pequeno ou pouco diverso pode reduzir a capacidade de generalização.
- Um modelo treinado em ENEM, SAS ou Poliedro pode ter desempenho inferior em
  outra banca devido a diferenças de estilo e elaboração.
- A previsão de uma questão inédita deve ser tratada como apoio à análise e
  priorização, não como substituta de uma calibração empírica.
- A qualidade depende da quantidade, diversidade e consistência das questões
  calibradas e das características extraídas.
- Imagens, fórmulas, tabelas e texto fora do padrão podem exigir processamento
  multimodal ou revisão humana.

## 12. Evolução futura

- Incorporar respostas reais de novas aplicações para recalibrar ou atualizar o
  modelo.
- Comparar estimativas com parâmetros oficiais quando publicados.
- Disponibilizar análise de erro por área, habilidade, banca e tipo de questão.
- Usar os parâmetros validados em um módulo posterior de proficiência (`θ`).
- Adicionar revisão humana e fluxo de aprovação para questões inéditas.

## 13. Requisitos da evolução web, dados e recomendações

### RF-10 — Camada de acesso a questões

O front-end deve consumir questões por meio de um cliente de dados isolado,
sem espalhar URLs ou detalhes da API ENEM.DEV pelos componentes da interface.
Essa camada deve permitir substituir a fonte externa por um repositório
Postgres/Prisma sem alterar o fluxo visual de consulta.

### RF-11 — Persistência futura com Postgres e Prisma

A evolução do produto deve prever um banco PostgreSQL acessado por Prisma para
persistir, no mínimo:

- questões e alternativas normalizadas;
- origem, ano, disciplina, habilidades e versões da fonte;
- parâmetros TRI calibrados e estimados;
- usuários, perfis de aluno e professor;
- tentativas, respostas e desempenho por questão;
- versões de features e modelos utilizados nas estimativas.

O schema Prisma deve manter chaves e relacionamentos explícitos, timestamps,
versionamento dos parâmetros e índices para consulta por ano, disciplina,
habilidade e faixa de dificuldade. A integração deve ser feita por uma camada
de repositórios/serviços, evitando acesso direto ao banco nos componentes
React.

### RF-12 — Recomendações baseadas em TRI

Em uma etapa posterior, o sistema deve oferecer recomendações diferentes para
alunos e professores:

- **Aluno:** sugerir questões compatíveis com a proficiência estimada, indicar
  progressão de dificuldade e priorizar habilidades com maior necessidade de
  prática;
- **Professor:** filtrar itens por área, habilidade, dificuldade, discriminação,
  taxa de acerto e objetivo pedagógico, permitindo montar listas ou simulados.

As recomendações devem usar apenas parâmetros cuja origem esteja identificada
como calibrada ou estimada. O usuário deve conseguir distinguir essa origem,
ver o motivo da recomendação e receber uma mensagem quando houver dados
insuficientes. O módulo não deve tratar uma estimativa de ML como verdade
oficial nem expor dados individuais de outros alunos.

### RNF-08 — Evolução sem acoplamento à interface

O contrato de dados apresentado à UI deve ser estável e independente do
provedor. A implementação inicial pode usar a API ENEM.DEV, mas deve permitir
adicionar um adaptador para Postgres/Prisma, cache e novos provedores sem
reescrever a tela de questão.