import type {PracticeField, PracticeTopic} from "./types";

export const INTERVIEW_FIELDS: Record<PracticeField, {
  label: string;
  areas: {value: PracticeTopic; label: string}[];
}> = {
  computer_science: {
    label: "Computer Science",
    areas: [
      {value: "system_design", label: "System design"},
      {value: "programming", label: "Programming language & technical depth"},
      {value: "problem_solving", label: "Problem solving / DSA"},
      {value: "behavioral", label: "Behavioral"},
      {value: "database", label: "Database"},
      {value: "architecture", label: "Architecture"},
    ],
  },
  physics: {
    label: "Physics",
    areas: [
      {value: "mechanics", label: "Mechanics"},
      {value: "electromagnetism", label: "Electromagnetism"},
      {value: "thermodynamics", label: "Thermodynamics"},
      {value: "quantum_physics", label: "Quantum physics"},
      {value: "optics", label: "Optics"},
      {value: "relativity", label: "Relativity"},
    ],
  },
  mathematics: {
    label: "Mathematics",
    areas: [
      {value: "algebra", label: "Algebra"},
      {value: "calculus", label: "Calculus"},
      {value: "probability_statistics", label: "Probability and statistics"},
      {value: "discrete_mathematics", label: "Discrete mathematics"},
      {value: "linear_algebra", label: "Linear algebra"},
      {value: "numerical_methods", label: "Numerical methods"},
    ],
  },
  business: {
    label: "Business",
    areas: [
      {value: "strategy", label: "Strategy"},
      {value: "finance", label: "Finance"},
      {value: "marketing", label: "Marketing"},
      {value: "operations", label: "Operations"},
      {value: "leadership", label: "Leadership"},
      {value: "economics", label: "Economics"},
    ],
  },
};

export const ALL_PRACTICE_TOPICS = new Set<PracticeTopic>(
  Object.values(INTERVIEW_FIELDS).flatMap(field => field.areas.map(area => area.value)),
);

export function areaLabel(topic: PracticeTopic): string {
  for (const field of Object.values(INTERVIEW_FIELDS)) {
    const area = field.areas.find(candidate => candidate.value === topic);
    if (area) return area.label;
  }
  return topic.replaceAll("_", " ");
}
