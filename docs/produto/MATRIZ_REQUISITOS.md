# Matriz de requisitos

![Progresso](https://geps.dev/progress/35)

Esta matriz acompanha a implementação do produto. O percentual é atualizado
automaticamente por `npm run requirements:progress`, contando cada identificador
de requisito e os marcadores `✅` abaixo. Cada requisito aparece uma única vez
para que o cálculo não seja inflado.

## Status

| ID | Status | Escopo |
|---|---|---|
| RF-01 | ⏳ | Importar e versionar microdados do ENEM |
| RF-02 | ⏳ | Armazenar parâmetros TRI calibrados e suas versões |
| RF-03 | ✅ | Consultar e renderizar questão ENEM por ano e número via ENEM.DEV |
| RF-04 | ⏳ | Receber questão inédita para estimativa |
| RF-05 | ⏳ | Extrair features textuais, estruturais, pedagógicas e estatísticas |
| RF-06 | ⏳ | Estimar os parâmetros `a`, `b` e `c` |
| RF-07 | ⏳ | Exibir resultado e interpretação dos parâmetros |
| RF-08 | ⏳ | Avaliar modelos com MAE, RMSE e R² |
| RF-09 | ⏳ | Auditar entradas, versões, resultados e falhas |
| RF-10 | ✅ | Isolar cliente da API em camada extensível para futura persistência |
| RF-11 | ⏳ | Persistir questões, perfis, respostas e parâmetros com Postgres/Prisma |
| RF-12 | ⏳ | Recomendar questões para alunos e professores com base em TRI |
| RNF-01 | ✅ | Interface web responsiva e extensível em Next.js |
| RNF-02 | ✅ | Tratar erros da API sem retorno de sucesso vazio |
| RNF-03 | ✅ | Cachear respostas externas sem executar treinamento na consulta |
| RNF-04 | ⏳ | Segurança, autenticação e proteção de dados |
| RNF-05 | ⏳ | Observabilidade e diagnóstico de processamento |
| RNF-06 | ⏳ | Acessibilidade e usabilidade |
| RNF-07 | ⏳ | Reprodutibilidade por versões de dados, features e modelos |
| RNF-08 | ✅ | Permitir evolução para banco relacional sem acoplamento à UI |

## Referência detalhada

Os requisitos de domínio, fluxos TRI, modelo de dados e critérios de aceitação
estão descritos em [../requisitos/requisitos.md](../requisitos/requisitos.md).
