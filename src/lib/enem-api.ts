import type { EnemQuestion } from "@/types/enem";

const API_BASE_URL = "https://api.enem.dev/v1";

export async function getEnemQuestion(
  year: number,
  index: number,
): Promise<EnemQuestion> {
  const response = await fetch(`${API_BASE_URL}/exams/${year}/questions/${index}`, {
    next: { revalidate: 3600 },
  });

  if (!response.ok) {
    throw new Error(`A API ENEM.DEV retornou HTTP ${response.status}.`);
  }

  return (await response.json()) as EnemQuestion;
}
