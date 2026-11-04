import Link from "next/link";
import { getEnemQuestion } from "@/lib/enem-api";

type SearchParams = Promise<{ ano?: string; questao?: string }>;

function parsePositiveInteger(value: string | undefined, fallback: number) {
  const parsed = Number(value);
  return Number.isInteger(parsed) && parsed > 0 ? parsed : fallback;
}

export default async function Home({
  searchParams,
}: {
  searchParams: SearchParams;
}) {
  const params = await searchParams;
  const year = parsePositiveInteger(params.ano, 2020);
  const index = parsePositiveInteger(params.questao, 1);
  let question;
  let error: string | undefined;

  try {
    question = await getEnemQuestion(year, index);
  } catch (requestError) {
    error =
      requestError instanceof Error
        ? requestError.message
        : "Não foi possível carregar a questão.";
  }

  return (
    <main className="shell">
      <header className="hero">
        <div>
          <span className="eyebrow">ESTIMADOR TRI · MVP</span>
          <h1>Questões ENEM, prontas para evoluir.</h1>
          <p>
            Consulte questões reais pela API ENEM.DEV. A base está organizada
            para receber parâmetros TRI e recomendações personalizadas.
          </p>
        </div>
        <div className="hero-badge">API ENEM.DEV</div>
      </header>

      <section className="panel search-panel" aria-labelledby="search-title">
        <div className="section-heading">
          <div>
            <span className="kicker">Banco de questões</span>
            <h2 id="search-title">Encontrar uma questão</h2>
          </div>
          <span className="status-dot">● online</span>
        </div>
        <form className="search-form">
          <label>
            Ano
            <input name="ano" type="number" min="2009" max="2023" defaultValue={year} />
          </label>
          <label>
            Número da questão
            <input name="questao" type="number" min="1" defaultValue={index} />
          </label>
          <button type="submit">Carregar questão</button>
        </form>
        <p className="hint">Fonte: api.enem.dev/v1 · dados públicos da comunidade.</p>
      </section>

      {error ? (
        <section className="panel error" role="alert">
          <strong>Não foi possível carregar este item.</strong>
          <p>{error}</p>
          <Link href="/">Tentar novamente com a questão 1 de 2020</Link>
        </section>
      ) : question ? (
        <article className="panel question-card">
          <div className="question-meta">
            <span className="pill">{question.year}</span>
            <span>{question.title}</span>
            <span>{question.discipline}</span>
            {question.language && <span>{question.language}</span>}
          </div>
          {question.context && (
            <div className="question-context">
              {question.context.split("\n").map((line, lineIndex) => (
                <p key={`${line}-${lineIndex}`}>{line || "\u00a0"}</p>
              ))}
            </div>
          )}
          {question.alternativesIntroduction && (
            <p className="introduction">{question.alternativesIntroduction}</p>
          )}
          <ol className="alternatives">
            {question.alternatives.map((alternative) => (
              <li key={alternative.letter}>
                <span className="letter">{alternative.letter}</span>
                <span>{alternative.text}</span>
              </li>
            ))}
          </ol>
          <div className="tri-preview">
            <div>
              <span className="kicker">Próxima camada</span>
              <strong>Parâmetros TRI</strong>
              <p>
                Este item está pronto para receber <b>a</b>, <b>b</b> e <b>c</b>{" "}
                da base calibrada.
              </p>
            </div>
            <span className="coming-soon">em breve</span>
          </div>
        </article>
      ) : null}
    </main>
  );
}
