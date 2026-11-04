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
├── produto/
│   └── MATRIZ_REQUISITOS.md
└── requisitos/
    └── requisitos.md
```

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

## Licença e fontes

Consulte as condições de uso da API ENEM.DEV e das fontes públicas utilizadas
antes de publicar dados derivados ou redistribuir conteúdo.
