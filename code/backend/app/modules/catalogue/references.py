"""Read-only access to pending local catalogue records for unverified fallback answers."""

from __future__ import annotations

import json
import logging
from functools import lru_cache
from pathlib import Path

from pydantic import ValidationError

from app.modules.catalogue.search import (
    NEED_CONCEPTS,
    NeedConcept,
    contains_phrase,
    expand_query,
    query_needs,
)
from app.modules.catalogue.service import _score, _tokens
from app.modules.eligibility.engine import localized
from app.schemas.service_record import ServiceCategory, ServiceRecord

logger = logging.getLogger("janmitra.catalogue.references")

_REFERENCE_STOPWORDS = frozenset(
    {
        "about",
        "anything",
        "area",
        "government",
        "help",
        "information",
        "maybe",
        "rural",
        "support",
        "assistance",
        "programme",
        "program",
        "yojana",
        "benefit",
        "benefits",
        "details",
        "documents",
        "apply",
        "application",
        "please",
        "tell",
        "family",
        "current",
    }
)


@lru_cache(maxsize=8)
def load_reference_records(directory: str) -> tuple[ServiceRecord, ...]:
    """Load valid bundled records without changing their pending-review status."""
    root = Path(directory)
    records: list[ServiceRecord] = []
    try:
        paths = sorted(root.glob("*.json"))
    except OSError as exc:
        logger.warning("reference catalogue is unavailable", extra={"error": str(exc)})
        return ()

    for path in paths:
        try:
            records.append(ServiceRecord.model_validate_json(path.read_text(encoding="utf-8")))
        except (OSError, ValidationError, json.JSONDecodeError) as exc:
            logger.warning(
                "skipping invalid reference record",
                extra={"path": str(path), "error": str(exc)},
            )
    return tuple(records)


def compact_records(
    records: tuple[ServiceRecord, ...], *, language: str = "en"
) -> list[dict[str, object]]:
    """Keep the model context useful while excluding rule-engine implementation details."""
    return [
        {
            "slug": record.slug,
            "name": localized(record.name, language),
            "aliases": record.aliases,
            "category": record.category.value,
            "description": localized(record.description, language),
            "first_action": (
                localized(min(record.steps, key=lambda step: step.order).instruction, language)
                if record.steps else None
            ),
            "benefit_summary": (
                localized(record.benefit_summary, language) if record.benefit_summary else None
            ),
            "eligibility_summary": (
                localized(record.eligibility_summary, language)
                if record.eligibility_summary
                else None
            ),
            "application_steps": [localized(step.instruction, language) for step in record.steps],
            "document_names": [localized(document.name, language) for document in record.documents],
            "citation": record.citation.model_dump(mode="json"),
            "publication_state": "unpublished_reference",
            "official_source": {
                "title": record.citation.source_title,
                "publisher": record.citation.publisher,
                "url": str(record.citation.source_url),
                "verification_state": record.citation.verification_state.value,
            },
        }
        for record in records
    ]


def ranked_records(
    records: tuple[ServiceRecord, ...],
    query: str,
    *,
    category: ServiceCategory | None = None,
    limit: int = 3,
) -> list[ServiceRecord]:
    expanded_query = expand_query(query)
    needs = list(query_needs(query))
    candidates = [r for r in records if category is None or r.category is category]
    query_tokens = _tokens(expanded_query) - _REFERENCE_STOPWORDS
    name_tokens = {
        r.slug: _tokens(" ".join([r.name.en, *r.aliases])) - _REFERENCE_STOPWORDS
        for r in candidates
    }
    frequency = {
        token: sum(token in tokens for tokens in name_tokens.values()) for token in query_tokens
    }
    known_slugs = {slug for concept in NEED_CONCEPTS for slug in concept.slugs}
    lexical = [
        r
        for r in candidates
        if (
            len(query_tokens & name_tokens[r.slug]) >= 2
            or (
                r.slug not in known_slugs
                and any(frequency[token] == 1 for token in query_tokens & name_tokens[r.slug])
            )
        )
    ]
    # Newly added schemes remain discoverable without editing the vocabulary.
    needs.extend(
        NeedConcept(f"catalogue:{r.slug}", (), (r.slug,))
        for r in lexical
        if r.slug not in known_slugs
    )
    # Acronyms, slugs, and full names are explicit scheme references. Descriptive
    # aliases ("crop insurance") remain needs so other concerns are not discarded.
    named = [
        r
        for r in candidates
        if any(
            contains_phrase(query, term)
            for term in (r.slug, r.name.en, *(a for a in r.aliases if a.isupper()))
        )
    ]
    if named or needs:
        selected = list(named)
        covered = {need.name for need in needs if any(r.slug in need.slugs for r in selected)}
        while len(selected) < limit:
            choices = []
            for record in candidates:
                if record in selected:
                    continue
                relevant = [need for need in needs if record.slug in need.slugs]
                if not relevant:
                    continue
                uncovered = sum(need.name not in covered for need in relevant)
                preference = max(1 / (1 + need.slugs.index(record.slug)) for need in relevant)
                choices.append((uncovered, preference, record.slug, record, relevant))
            if not choices:
                break
            choices.sort(key=lambda item: (-item[0], -item[1], item[2]))
            _, _, _, chosen, relevant = choices[0]
            # A focused named lookup already supplies all recognized concerns.
            if named and all(need.name in covered for need in needs):
                break
            selected.append(chosen)
            covered.update(need.name for need in relevant)
        return selected[:limit]
    scored = [
        (*_score(record, expanded_query, query_tokens), record)
        for record in records
        if category is None or record.category is category
    ]
    # Sparse incidental overlap in a personal story is not evidence of a scheme
    # match. Without a recognized need, require a full descriptive alias/name.
    scored = [
        item
        for item in scored
        if item[2] in lexical
        or (
            item[1] == "alias"
            and any(contains_phrase(query, alias) for alias in (item[2].name.en, *item[2].aliases))
        )
    ]
    scored.sort(key=lambda item: (-item[0], item[2].slug))
    return [record for score, _, record in scored[:limit] if score >= 0.5]


def deterministic_answer(
    records: tuple[ServiceRecord, ...],
    query: str,
    *,
    category: ServiceCategory | None = None,
) -> str:
    """Last-resort useful text when Gemini Lite itself is unavailable."""
    ranked = ranked_records(records, query, category=category, limit=2)
    if not ranked:
        return (
            "This is general information that Janmitra has not yet verified and it may be "
            "outdated. Government support depends on your state, location, occupation, and "
            "need. Please describe whether you need a loan, insurance, pension, grant, bank "
            "account, housing, ration, or employment help so I can narrow it down."
        )

    details = []
    for record in ranked:
        benefit = record.benefit_summary.en if record.benefit_summary else record.description.en
        parts = [f"{record.name.en}: {benefit}"]
        if record.eligibility_summary:
            parts.append(record.eligibility_summary.en)
        if record.documents:
            parts.append("Documents to prepare: " + "; ".join(d.name.en for d in record.documents))
        if record.steps:
            parts.append("How to apply: " + " ".join(s.instruction.en for s in record.steps))
        details.append(" ".join(parts))
    return " ".join(details) + " This is reference guidance, not an official eligibility decision."
