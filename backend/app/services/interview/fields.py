"""Supported interview fields and their selectable assessment areas."""

from typing import TypedDict


class InterviewFieldDefinition(TypedDict):
    label: str
    areas: dict[str, tuple[str, str]]


INTERVIEW_FIELDS: dict[str, InterviewFieldDefinition] = {
    "computer_science": {
        "label": "Computer Science",
        "areas": {
            "system_design": ("System design", "Architecture, scale, reliability and trade-offs"),
            "programming": ("Programming", "Languages, implementation choices and technical depth"),
            "problem_solving": (
                "Problem solving",
                "Algorithms, decomposition, edge cases and complexity",
            ),
            "behavioral": ("Behavioral", "Ownership, collaboration and learning from experience"),
            "database": (
                "Database",
                "Schema design, indexing, query performance and data modeling",
            ),
            "architecture": (
                "Architecture",
                "Component boundaries, integrations and maintainability",
            ),
        },
    },
    "physics": {
        "label": "Physics",
        "areas": {
            "mechanics": ("Mechanics", "Motion, forces, energy, momentum and rotational systems"),
            "electromagnetism": (
                "Electromagnetism",
                "Electric and magnetic fields, circuits and waves",
            ),
            "thermodynamics": ("Thermodynamics", "Heat, work, entropy and statistical behavior"),
            "quantum_physics": (
                "Quantum physics",
                "Quantum states, measurement and microscopic systems",
            ),
            "optics": ("Optics", "Geometric and wave optics, interference and diffraction"),
            "relativity": ("Relativity", "Special and general relativity and spacetime reasoning"),
        },
    },
    "mathematics": {
        "label": "Mathematics",
        "areas": {
            "algebra": ("Algebra", "Equations, structures, transformations and abstract reasoning"),
            "calculus": ("Calculus", "Limits, derivatives, integrals and multivariable analysis"),
            "probability_statistics": (
                "Probability and statistics",
                "Randomness, inference and data analysis",
            ),
            "discrete_mathematics": (
                "Discrete mathematics",
                "Logic, combinatorics, graphs and proofs",
            ),
            "linear_algebra": (
                "Linear algebra",
                "Vectors, matrices, linear maps and eigenproblems",
            ),
            "numerical_methods": (
                "Numerical methods",
                "Approximation, numerical stability and computation",
            ),
        },
    },
    "business": {
        "label": "Business",
        "areas": {
            "strategy": ("Strategy", "Competitive positioning, growth and strategic trade-offs"),
            "finance": (
                "Finance",
                "Financial analysis, valuation, budgeting and capital allocation",
            ),
            "marketing": ("Marketing", "Customer insight, positioning, channels and measurement"),
            "operations": ("Operations", "Processes, capacity, quality and supply chains"),
            "leadership": ("Leadership", "People leadership, decisions, communication and change"),
            "economics": ("Economics", "Markets, incentives, pricing and macroeconomic context"),
        },
    },
}

INTERVIEW_FIELD_IDS = tuple(INTERVIEW_FIELDS)
ALL_AREA_IDS = frozenset(
    area_id for field in INTERVIEW_FIELDS.values() for area_id in field["areas"]
)


def areas_for_field(field_type: str) -> dict[str, tuple[str, str]]:
    field = INTERVIEW_FIELDS.get(field_type)
    if field is None:
        return {}
    return field["areas"]


def field_label(field_type: str) -> str:
    field = INTERVIEW_FIELDS.get(field_type)
    return field["label"] if field else field_type.replace("_", " ").title()


def expand_areas(field_type: str, selected: list[str]) -> list[str]:
    """Expand the exclusive ``all_areas`` choice to concrete prompt areas."""
    areas = areas_for_field(field_type)
    if selected == ["all_areas"]:
        return list(areas)
    return list(dict.fromkeys(selected))
