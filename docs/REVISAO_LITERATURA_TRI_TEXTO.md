# Revisão de literatura: previsão de parâmetros TRI a partir de questões

Busca realizada em 12/11/2026 em repositórios de publicações (ACM/SoLAR,
ACL Anthology, arXiv, repositório institucional da UFF e periódicos), usando
combinações de `item difficulty prediction`, `IRT parameter prediction`,
`item text`, `embeddings`, `ENEM` e `TRI`. Esta é uma revisão dirigida para
posicionar o projeto, não uma revisão sistemática exaustiva.

## Resultado principal

O problema **já foi estudado com questões do ENEM**. Marinho et al. (2023)
usaram representações de texto e redes neurais para prever parâmetros TRI;
a tese de Marinho (2025) amplia a abordagem. Portanto, não é adequado apresentar
"prever `a`, `b` e `c` do ENEM pelo texto" como uma ideia inédita. Há espaço
para uma contribuição em **base auditável, reprodução e avaliação de utilidade
prática**, se os experimentos forem rigorosos.

## Trabalhos diretamente relacionados

| Trabalho | Dados e tarefa | Resultado/implicação para este projeto |
| --- | --- | --- |
| [Marinho et al., LAK 2023](https://doi.org/10.1145/3576050.3576139); [versão acessível na tese da UFF](https://app.uff.br/riuff/handle/1/39803) | Texto de questões do ENEM; modelo neural com perda baseada na curva característica do item. Treino em 2009–2019, avaliação em 2020–2021. | Erro absoluto médio de aproximadamente 70 pontos para `b` na escala de proficiência. É o antecedente mais próximo e deve ser discutido em destaque. |
| [Marinho, tese UFF, 2025](https://app.uff.br/riuff/handle/1/39803) | 2.578 enunciados de 14 anos do ENEM; compara encoders de português, representações relativas e arquiteturas para parâmetros TRI. | Mostra que uma implementação com encoder e regressão não é inédita; oferece protocolo temporal e métricas de curva/nota como referências. |
| [Brant, Kühn e Pang, arXiv 2026](https://arxiv.org/abs/2602.06631) **(preprint)** | 1.031 questões do ENEM, 2017–2022; dez LLMs estimam dificuldade TRI. | Avalia ordenação, erro absoluto e itens visuais. A média foi forte como referência para erro; estimativas de LLMs apresentaram limitações de calibração e multimodalidade. |
| [Chen e Chen, arXiv 2026](https://arxiv.org/abs/2607.07141) **(preprint)** | Embeddings e regressão regularizada para parâmetros 1PL/2PL/3PL em bancos de matemática e medicina. | `b` foi mais previsível; `a` e `c` do 3PL foram menos estáveis. Recomendam validação cruzada repetida e examinar a confiabilidade dos rótulos. |
| [Benedetto et al., BEA 2021](https://aclanthology.org/2021.bea-1.16/) | Transformers para dificuldade de questões de múltipla escolha em bases pública e privada. | Referência de método; texto e formato da questão podem melhorar estimativas de dificuldade. |
| [Yancey et al., BEA 2024](https://aclanthology.org/2024.bea-1.35/) | BERT-IRT para pré-testes do Duolingo English Test. | Uso próximo ao banco de questões: embeddings como informação auxiliar para reduzir, não eliminar, a coleta de respostas. |
| [Han et al., AIME-Con 2025](https://aclanthology.org/2025.aimecon-main.27.pdf) | Mais de mil itens de língua inglesa; texto, atributos estruturados, LLMs ajustados e CatBoost para dificuldade/discriminação. | Metadados ajudam, mas a arquitetura vencedora varia com o parâmetro; resultados de discriminação foram distintos dos de dificuldade. |
| [Palomino e Paassen, RANLP 2025](https://aclanthology.org/2025.ranlp-1.99/) | 935 itens profissionais alemães com dificuldade derivada de TRI; benchmark de classificadores. | Exemplo de avaliação em base pequena e real, próxima ao tamanho inicial do nosso dataset. |
| [Estudo de Matemática do ENEM, 2026](https://revistas.uece.br/index.php/impa/article/view/17869) | 661 itens de 2009–2023; regressão de `b` em comprimento do texto e presença de figuras/gráficos/tabelas. | Justifica medir características visuais e textuais além do embedding; não estuda previsão conjunta de `a`, `b` e `c`. |

## Comparação com o projeto atual

O pipeline local liga PDFs de provas azuis à tabela oficial `ITENS_PROVA`
por ano, área, posição, cor e `CO_PROVA`. O código verifica `CO_PROVA` por
comparação com gabaritos oficiais, registra a evidência e separa pares
ambíguos. A base atual contém 3.088 itens únicos no treino/avaliação depois
dos filtros. O modelo usa MiniLM multilíngue, metadados, regressão e baselines
por área/ano. Na divisão atual, a previsão de `b` pelo Elastic Net teve
MAE 0,684 na escala bruta dos microdados, contra 0,690 do baseline por
área/ano; `a` e `c` não apresentaram ganho consistente.

**Não comparar diretamente** MAE 0,684 com os 70 pontos de Marinho: os trabalhos
usam escalas, conjuntos de itens, pré-processamento e divisão temporal
diferentes. Uma comparação válida requer reproduzir a mesma transformação
de escala e o mesmo conjunto de teste.

## Questão de pesquisa defensável

> Em questões inéditas de um ano do ENEM, embeddings e metadados do item
> melhoram a estimativa preliminar de dificuldade TRI em relação a baselines
> por área/ano? O ganho permanece quando se exige pareamento verificado por
> gabarito e se avalia separadamente itens com elementos visuais?

O título deve explicitar **estimativa preliminar**. A calibração TRI em sentido
psicométrico usa respostas de participantes; prever parâmetros pelo texto
serve como apoio antes da aplicação, não como substituto automaticamente
equivalente à calibração.

## Experimentos prioritários para sustentar a contribuição

1. Separar treino e teste por **ano inteiro**, com um ou mais anos recentes
   reservados para teste. O split aleatório atual pode superestimar a utilidade
   para itens futuros.
2. Comparar `b` com média global, média por área/ano e modelos de texto,
   reportando MAE, RMSE, R² e correlação de Spearman; calcular incerteza por
   reamostragem. Relatar `a` e `c` como tarefas secundárias.
3. Fazer ablação: metadados isolados, embedding isolado e combinação. Verificar
   se rótulos pedagógicos externos foram produzidos sem acesso à dificuldade
   oficial para evitar vazamento.
4. Separar itens com gráficos, imagens e tabelas dos itens totalmente textuais.
   Um encoder de texto não vê informações importantes das figuras.
5. Se o objetivo final for montar provas simuladas, avaliar também a utilidade
   das previsões para ordenar itens por dificuldade ou construir curvas TRI,
   sempre comparando com parâmetros oficiais.

## Conclusão

A contribuição acadêmica mais plausível é uma **reprodução crítica e benchmark
auditável para o ENEM**, com avaliação temporal, baselines, análise de
multimodalidade e limites por parâmetro. A originalidade não deve ser atribuída
à simples regressão de `a`, `b` e `c` a partir de texto, já explorada em
trabalhos anteriores.
