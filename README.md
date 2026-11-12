# Plataforma de Questões com Estimador TRI

Plataforma web para consulta de questões do ENEM e futura estimativa dos
parâmetros da Teoria de Resposta ao Item (TRI).

## Ideia principal

O projeto começa oferecendo uma interface simples para consultar e visualizar
questões reais do ENEM por ano e número, utilizando a API pública
[ENEM.DEV](https://enem.dev/).

A evolução planejada é integrar os dados de questões, respostas e parâmetros
TRI para:

- consultar questões já calibradas a partir dos microdados;
- estimar os parâmetros `a` (discriminação), `b` (dificuldade) e `c` (acerto
  ao acaso) de questões inéditas;
- recomendar questões para alunos de acordo com sua proficiência e necessidades
  de aprendizagem;
- permitir que professores filtrem questões e montem listas ou simulados por
  área, habilidade e dificuldade.

Questões calibradas e estimativas produzidas por aprendizado de máquina serão
identificadas separadamente. Uma estimativa não será apresentada como parâmetro
oficial sem validação empírica.

## Estado atual

- Front-end responsivo em Next.js.
- Consulta server-side à API ENEM.DEV.
- Busca por ano e número da questão.
- Renderização de contexto, enunciado e alternativas.
- Tratamento de erros da API.
- Cache das respostas externas.
- Cliente da API isolado para futura substituição por um repositório
  Postgres/Prisma.
- Matriz de requisitos com cálculo automático de progresso.

## Tecnologias

- Next.js
- React
- TypeScript
- API ENEM.DEV
- Futuramente: PostgreSQL, Prisma e modelos de aprendizado de máquina.

## Como executar

Requisitos: Node.js 22 ou superior.

```bash
npm install
npm run dev
```

Abra [http://localhost:3000](http://localhost:3000) no navegador.

Para validar a versão de produção:

```bash
npm run build
npm start
```

## Estrutura principal

```text
src/
├── app/
│   ├── globals.css       # estilos da interface
│   ├── layout.tsx        # metadados e layout global
│   └── page.tsx          # tela de consulta de questões
├── lib/
│   └── enem-api.ts       # cliente isolado da API ENEM.DEV
└── types/
    └── enem.ts           # tipos das respostas da API
docs/
├── microdados-enem-e-api.md
├── produto/
│   └── MATRIZ_REQUISITOS.md
└── requisitos/
    └── requisitos.md
```

## Pipeline local de extração e IA

O extrator lê diretamente os ZIPs oficiais do INEP e não expande o CSV grande
com respostas individuais. As dependências Python estão em
[`requirements.txt`](requirements.txt). Use Python 3.12; Python 3.15 ainda não
tem wheels disponíveis para todas as dependências científicas usadas aqui.

Na raiz do projeto, crie o ambiente e instale as dependências:

```bash
python3.12 -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Depois, coloque os ZIPs oficiais em `dados/microdados/` e execute o pipeline
completo para provas azuis:

```bash
python -m python.main --color AZUL
```

O pipeline preserva os ZIPs por padrão. Para retomar etapas, pular redução,
extração ou treino, ou remover os ZIPs depois de validar a extração, consulte
[python/README.md](python/README.md). Os pesos MiniLM são baixados na primeira
execução do treino, então será necessária conexão com a internet ou cache local.
OCR é opcional; para usá-lo instale Tesseract e os idiomas `por` e `eng`, e
adicione `--ocr` ao comando. A extração de texto e o pareamento com `CO_PROVA`
precisam de auditoria antes de tratar as métricas do modelo como resultado final.

O pipeline grava os arquivos intermediários em `dados/extraidos/` e
`dados/processados/`; esses dados locais estão excluídos do Git.

### Extrair arquivos necessários dos ZIPs do INEP

Para comparar a estrutura dos pacotes e extrair somente as tabelas de itens,
provas, gabaritos e documentos de layout (sem expandir o CSV de respostas):

```bash
python python/extrair_pacotes_inep.py \
  --input dados/microdados \
  --output dados/extraidos
```

O script gera `estrutura_pacote.json` por edição e
`relatorio_estrutura.json` consolidado. Os ZIPs originais permanecem intactos.
A estrutura conceitual é estável, mas nomes de arquivos, dias, cadernos e
códigos mudam entre anos; o relatório preserva essas diferenças.

## API utilizada

O front-end utiliza:

```text
GET https://api.enem.dev/v1/exams/{ano}/questions/{numero}
```

Os dados são fornecidos pelo projeto comunitário ENEM.DEV. A API não é
afiliada, endossada ou patrocinada pelo INEP ou pelo MEC.

## Próximas etapas

1. Importar e versionar os microdados do ENEM.
2. Armazenar parâmetros TRI calibrados.
3. Criar o formulário para questões inéditas.
4. Treinar e validar modelos para estimar `a`, `b` e `c`.
5. Migrar a persistência para PostgreSQL com Prisma.
6. Criar perfis de alunos e professores.
7. Implementar recomendações baseadas em TRI.

O detalhamento completo está em
[docs/requisitos/requisitos.md](docs/requisitos/requisitos.md), e o
acompanhamento de implementação está em
[docs/produto/MATRIZ_REQUISITOS.md](docs/produto/MATRIZ_REQUISITOS.md).

A pesquisa sobre a organização dos microdados oficiais e a cobertura da API
está em [docs/microdados-enem-e-api.md](docs/microdados-enem-e-api.md).

## Licença e fontes

Consulte as condições de uso da API ENEM.DEV e das fontes públicas utilizadas
antes de publicar dados derivados ou redistribuir conteúdo.
