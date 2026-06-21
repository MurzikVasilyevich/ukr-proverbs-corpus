from __future__ import annotations

import pandas as pd

from core.schema import Annotation, CanonicalRecord


def load(proverbs_path: str, links_path: str) -> list[CanonicalRecord]:
    proverbs = pd.read_csv(proverbs_path, dtype=str, keep_default_na=False)
    links = pd.read_csv(links_path, dtype=str, keep_default_na=False)
    # normalise column names (real files ship a UTF-8 BOM on the first header)
    proverbs.columns = [c.lstrip("﻿").strip() for c in proverbs.columns]
    links.columns = [c.lstrip("﻿").strip() for c in links.columns]

    source_by_proverb = dict(zip(links["Proverb"], links["Source"]))

    records: list[CanonicalRecord] = []
    for _, row in proverbs.iterrows():
        text = row["text"].strip()
        if not text:
            continue
        pid = row["id"].strip()
        source = source_by_proverb.get(pid, "Mlodzynskyi2009")
        records.append(
            CanonicalRecord(
                text=text,
                keyword="",
                annotations=[Annotation(source=source, ref=pid)],
            )
        )
    return records
