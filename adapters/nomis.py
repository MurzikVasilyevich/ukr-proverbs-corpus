from __future__ import annotations

import pandas as pd

from core.schema import Annotation, CanonicalRecord

SOURCE = "Nomis1864"


def load(path: str) -> list[CanonicalRecord]:
    df = pd.read_csv(path, dtype=str, keep_default_na=False)
    records: list[CanonicalRecord] = []
    for _, row in df.iterrows():
        text = row["text"].strip()
        if not text:
            continue
        records.append(
            CanonicalRecord(
                text=text,
                keyword="",
                annotations=[Annotation(source=SOURCE, ref=row["ref"].strip())],
            )
        )
    return records
