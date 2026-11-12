# Microdados do ENEM e cobertura da API

Pesquisa realizada em **04/11/2026** para orientar a ingestão dos dados da
plataforma e a futura calibração dos parâmetros TRI.

## Resumo executivo

- O portal oficial do INEP disponibiliza pacotes anuais de microdados do ENEM
  de **1998 a 2025**.
- A página oficial descreve os microdados como a menor unidade de
  desagregação e informa que os pacotes incluem provas, gabaritos, informações
  dos itens, notas e questionários respondidos pelos inscritos.
- A API ENEM.DEV consultada em `https://api.enem.dev/v1/exams` disponibiliza
  provas de **2009 a 2023**, inclusive.
- Portanto, há **15 anos em comum** entre as fontes: 2009–2023.
- Há microdados oficiais sem cobertura correspondente na API para **1998–2008
  e 2024–2025**.
- A API é adequada para renderizar o conteúdo de questões no front-end, mas não
  substitui os microdados para calibração TRI: ela não fornece, por si só, a
  população de respostas necessária para estimar `a`, `b` e `c`.

## Fontes consultadas

| Fonte | Finalidade | Resultado observado |
|---|---|---|
| [Página oficial de microdados do ENEM](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados/enem) | Downloads e descrição dos pacotes | Links de 1998 a 2025; página atualizada em 01/09/2026 |
| [Página geral de microdados do INEP](https://www.gov.br/inep/pt-br/acesso-a-informacao/dados-abertos/microdados) | Privacidade e política de divulgação | Dados históricos permanecem disponíveis com técnicas de anonimização |
| [Endpoint de provas da API](https://api.enem.dev/v1/exams) | Lista de anos expostos pela API | 2009 a 2023 |
| [Documentação da API](https://docs.enem.dev/introduction) | Contrato e limites conceituais | API pública comunitária para provas e questões |
| [Endpoint de questões](https://docs.enem.dev/api-reference/quest%C3%B5es/listar-quest%C3%B5es) | Formato de consulta por ano | `GET /exams/{year}/questions` |

As fontes externas podem ser atualizadas. A lista abaixo representa a
consulta realizada na data indicada neste documento.

## Anos disponíveis para download no INEP

A página oficial apresenta um arquivo `microdados_enem_<ano>.zip` para cada
ano da tabela:

| Período | Anos disponíveis no INEP | Situação |
|---|---:|---|
| Histórico inicial | 1998–2008 | Microdados oficiais; não aparecem na lista atual da API |
| Interseção | 2009–2023 | Microdados oficiais e questões expostas pela API |
| Mais recentes | 2024–2025 | Microdados oficiais; não aparecem na lista atual da API |

Os links seguem o padrão:

```text
https://download.inep.gov.br/microdados/microdados_enem_<ano>.zip
```

Além do pacote principal, a página oficial disponibiliza, para alguns anos
recentes, arquivos específicos de competências da redação, por exemplo:

```text
https://download.inep.gov.br/microdados/competencias_redacao_enem_<ano>.zip
```

Esse arquivo de redação deve ser tratado como fonte complementar, não como
substituto do pacote principal.

### Tamanho e operação de download

Os pacotes são grandes e variam bastante por ano. Em uma verificação por
cabeçalho HTTP, os arquivos observados foram aproximadamente:

| Ano | Tamanho aproximado |
|---:|---:|
| 1998 | 24 MiB |
| 2000 | 48 MiB |
| 2009 | 528 MiB |
| 2023 | 524 MiB |
| 2025 | 988 MiB |

O tamanho não deve ser fixado no código. A rotina de ingestão deve usar
download por streaming, validar o tamanho/checksum quando disponível, manter o
arquivo original fora do banco e permitir retomada ou reprocessamento.

## Organização lógica dos microdados

O INEP entrega os dados como pacotes ZIP anuais. A descrição oficial indica que
o conteúdo cobre as seguintes camadas:

1. **Identificação da edição e do participante**
   - ano/edição;
   - identificadores anonimizados;
   - presença, atendimento especializado e informações de aplicação, quando
     divulgadas.
2. **Respostas aos itens**
   - respostas marcadas pelos participantes;
   - situação da resposta e variáveis necessárias para relacionar participante,
     caderno e item.
3. **Provas, itens e gabaritos**
   - códigos e posições dos itens;
   - área/prova, cor ou caderno;
   - gabarito e informações do item;
   - arquivos de prova e gabarito que permitem reconstruir o enunciado e as
     alternativas, quando fornecidos no pacote.
4. **Notas**
   - proficiências/notas das áreas objetivas;
   - nota de redação e variáveis relacionadas, conforme a edição.
5. **Questionário do participante**
   - respostas socioeconômicas e educacionais divulgadas de forma anonimizada.
6. **Documentação**
   - leia-me, dicionários de dados, layouts e códigos de categorias.

Os nomes das colunas, categorias, arquivos e regras de anonimização podem mudar
entre edições. Por isso, a ingestão não deve assumir que o layout de 2009 é
idêntico ao de 2023 ou 2025. O dicionário e o leia-me de cada ZIP devem ser
tratados como contrato da respectiva edição.

### Modelo de armazenamento recomendado

Para a plataforma, a organização física dos ZIPs deve ser convertida em um
modelo canônico:

```text
Fonte
└── Edição (ano)
    ├── Participante anonimizado
    ├── Prova/Caderno
    ├── Questão/Item
    ├── Alternativa/Gabarito
    ├── Resposta
    ├── Nota/Proficiência
    ├── Questionário
    └── Dicionário/Layout
```

O campo `source_version` deve guardar o ano, nome do arquivo, data de
download, tamanho e hash. O campo `schema_version` deve identificar o
mapeamento canônico aplicado ao layout original.

## Organização e cobertura da API ENEM.DEV

### Lista de provas

O endpoint:

```http
GET https://api.enem.dev/v1/exams
```

retorna, por ano:

- título da prova;
- ano;
- disciplinas;
- idiomas disponíveis.

Na consulta realizada, a resposta veio em ordem decrescente de 2023 até 2009.
As quatro áreas aparecem como:

- Ciências Humanas e suas Tecnologias;
- Ciências da Natureza e suas Tecnologias;
- Linguagens, Códigos e suas Tecnologias;
- Matemática e suas Tecnologias.

Os idiomas variam por edição: 2009 não retornou idiomas, 2011 retornou
Espanhol, e as demais edições listadas retornaram Espanhol e/ou Inglês.

### Questões de uma prova

O endpoint documentado é:

```http
GET https://api.enem.dev/v1/exams/{year}/questions
```

Para uma questão específica:

```http
GET https://api.enem.dev/v1/exams/{year}/questions/{index}
```

O objeto de questão observado contém:

```text
title
index
discipline
language
year
context
files
correctAlternative
alternativesIntroduction
alternatives[]
```

Cada alternativa contém letra, texto, arquivo opcional e indicador de
correção. Esse formato é apropriado para a renderização atual do front-end,
mas não contém os microdados de respostas dos participantes.

## Comparação direta

| Ano | Download oficial INEP | API ENEM.DEV na consulta | Uso recomendado |
|---:|:---:|:---:|---|
| 1998–2008 | Sim | Não | Ingestão própria; não assumir conteúdo renderizável pela API |
| 2009–2023 | Sim | Sim | Usar API para consulta e microdados para calibração/validação |
| 2024–2025 | Sim | Não | Preparar ingestão própria; aguardar ou não depender da API |

### Conclusão operacional

1. **Front-end atual:** continuar usando ENEM.DEV para consulta rápida de
   questões nos anos 2009–2023.
2. **Pipeline TRI:** baixar os microdados oficiais por ano, começando pela
   interseção 2009–2023, e relacionar respostas, itens, gabaritos e notas.
3. **Anos fora da API:** manter 1998–2008 e 2024–2025 como fontes oficiais
   disponíveis para futura ingestão, sem bloquear o produto caso a API não os
   ofereça.
4. **Fonte de verdade:** considerar os microdados e seus dicionários como fonte
   de calibração; considerar a API como fonte de apresentação/conveniência.
5. **Reconciliação:** criar uma tabela de correspondência entre `ano`,
   `index`, código do item, prova/caderno, disciplina e gabarito. O número da
   questão na API não deve ser usado sozinho como chave universal.

## Riscos e cuidados

- A divulgação dos microdados está sujeita a anonimização e regras da LGPD; não
  tentar reidentificar participantes.
- A presença de um ZIP oficial não garante que todos os campos necessários
  para uma calibração TRI estejam disponíveis naquela edição.
- Layouts históricos podem ter codificações e nomes de coluna diferentes.
- Questões e imagens da API podem ter tratamento diferente dos arquivos
  originais do INEP; validar a correspondência antes de treinar modelos.
- Não baixar todos os anos durante o build ou em requisições web. A ingestão
  deve ser um processo assíncrono, versionado e observável.
- A API ENEM.DEV é um projeto comunitário e informa que não é afiliada,
  endossada ou patrocinada pelo INEP/MEC.

## Próximos passos técnicos

- Criar um catálogo de edições com status `disponivel`, `baixada`,
  `extraida`, `normalizada` e `validada`.
- Implementar downloader com streaming, retry, checksum e armazenamento
  externo dos ZIPs.
- Extrair o dicionário de cada edição antes de carregar CSVs.
- Mapear layouts anuais para tabelas canônicas no Postgres.
- Validar a chave de ligação entre questão, caderno, gabarito e resposta.
- Comparar amostras da API com os arquivos de prova/gabarito oficiais.
- Registrar no modelo TRI a edição e o layout usados no treinamento.
