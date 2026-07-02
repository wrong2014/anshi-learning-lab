from __future__ import annotations

from difflib import SequenceMatcher

from .curriculum_models import (
    CurriculumEvidencePage,
    KnowledgePointBatch,
)


def _normalized_with_offsets(text: str) -> tuple[str, list[int]]:
    characters: list[str] = []
    offsets: list[int] = []
    for index, character in enumerate(text):
        if character.isalnum():
            characters.append(character)
            offsets.append(index)
    return "".join(characters), offsets


def repair_point_citations(
    batch: KnowledgePointBatch,
    evidence_pages: list[CurriculumEvidencePage],
    *,
    minimum_match_chars: int = 16,
    minimum_match_ratio: float = 0.35,
) -> tuple[KnowledgePointBatch, list[dict]]:
    """Repair only high-confidence OCR excerpt/page-boundary mismatches.

    The replacement is always a continuous raw slice from one supplied evidence
    page. Knowledge-point content and every non-citation field remain unchanged.
    """

    evidence_by_key = {
        (page.source_id, page.logical_page): page
        for page in evidence_pages
        if page.logical_page is not None
    }
    payload = batch.model_dump(mode="json")
    repairs: list[dict] = []

    for point in payload["points"]:
        for citation in point["citations"]:
            original_excerpt = citation["excerpt"]
            excerpt_normalized, _ = _normalized_with_offsets(original_excerpt)
            start = citation.get("page_start")
            end = citation.get("page_end")

            if start is not None and start == end:
                page = evidence_by_key.get((citation["source_id"], start))
                if page:
                    page_normalized, _ = _normalized_with_offsets(page.text)
                    if excerpt_normalized and excerpt_normalized in page_normalized:
                        continue

            candidate_pages = []
            cited_page_numbers: set[int] = set()
            if start is not None and end is not None:
                low, high = sorted((start, end))
                cited_page_numbers = set(range(low, high + 1))
                candidate_pages = [
                    page
                    for logical_page in range(low, high + 1)
                    if (page := evidence_by_key.get((citation["source_id"], logical_page)))
                ]
            elif start is not None:
                cited_page_numbers = {start}
                page = evidence_by_key.get((citation["source_id"], start))
                candidate_pages = [page] if page else []

            # A model can copy the OCR text exactly while reporting the printed
            # page number instead of the evidence pack's logical page. Search
            # the rest of this task's already-authorized evidence pages too,
            # but require a much stronger match before changing the page.
            candidate_page_keys = {(page.source_id, page.logical_page) for page in candidate_pages}
            candidate_pages.extend(
                page
                for page in evidence_pages
                if page.source_id == citation["source_id"]
                and (page.source_id, page.logical_page) not in candidate_page_keys
            )

            best: tuple[int, CurriculumEvidencePage, str] | None = None
            for page in candidate_pages:
                page_normalized, offsets = _normalized_with_offsets(page.text)
                if not excerpt_normalized or not page_normalized:
                    continue
                match = SequenceMatcher(
                    None,
                    excerpt_normalized,
                    page_normalized,
                    autojunk=False,
                ).find_longest_match()
                if match.size == 0:
                    continue
                raw_start = offsets[match.b]
                raw_end = offsets[match.b + match.size - 1] + 1
                replacement = page.text[raw_start:raw_end]
                if best is None or match.size > best[0]:
                    best = (match.size, page, replacement)

            if best is None:
                continue
            match_chars, page, replacement = best
            match_ratio = match_chars / max(1, len(excerpt_normalized))
            if match_chars < minimum_match_chars or match_ratio < minimum_match_ratio:
                continue
            if page.logical_page not in cited_page_numbers and match_ratio < 0.80:
                continue

            repairs.append(
                {
                    "point_id": point["id"],
                    "source_id": citation["source_id"],
                    "original_page_start": start,
                    "original_page_end": end,
                    "original_excerpt": original_excerpt,
                    "repaired_page": page.logical_page,
                    "repaired_excerpt": replacement,
                    "matched_characters": match_chars,
                    "match_ratio": round(match_ratio, 4),
                }
            )
            citation["page_start"] = page.logical_page
            citation["page_end"] = page.logical_page
            citation["excerpt"] = replacement

    return KnowledgePointBatch.model_validate(payload), repairs
