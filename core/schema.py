from __future__ import annotations

from dataclasses import dataclass, field

SOURCE_PRIORITY: dict[str, int] = {
    "Franko1901": 0,
    "Mlodzynskyi2009": 1,
    "Ilkevich1841": 2,
}


@dataclass
class Annotation:
    source: str
    ref: str = ""
    explanation: str = ""


@dataclass
class CanonicalRecord:
    text: str
    normalized_text: str = ""
    keyword: str = ""
    annotations: list[Annotation] = field(default_factory=list)
    category: str = ""
    variant_group: str = ""
    id: str = ""

    def sources(self) -> list[str]:
        return [a.source for a in self.annotations]

    def source_refs(self) -> list[str]:
        return [a.ref for a in self.annotations]

    def csv_explanation(self) -> str:
        with_expl = [a for a in self.annotations if a.explanation]
        if not with_expl:
            return ""
        with_expl.sort(key=lambda a: SOURCE_PRIORITY.get(a.source, 99))
        return with_expl[0].explanation
