export type EnemAlternative = {
  letter: string;
  text: string;
  file: string | null;
  isCorrect: boolean;
};

export type EnemQuestion = {
  title: string;
  index: number;
  discipline: string;
  language?: string;
  year: number;
  context?: string;
  files: string[];
  correctAlternative?: string;
  alternativesIntroduction?: string;
  alternatives: EnemAlternative[];
};
