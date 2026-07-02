from __future__ import annotations

from uuid import uuid4

from .curriculum_models import (
    CurriculumEvidencePack,
    CurriculumKnowledgeNetwork,
    CurriculumPipelineRequest,
    CurriculumReleaseBundle,
    CurriculumReleaseManifest,
    CurriculumSourceCatalog,
)
from .curriculum_validators import validate_network
from .models import IssueSeverity, stable_digest
from .repository import FactoryRepository


def publish_curriculum_network(
    network: CurriculumKnowledgeNetwork,
    *,
    request: CurriculumPipelineRequest,
    catalog: CurriculumSourceCatalog,
    evidence: CurriculumEvidencePack,
    version: str,
    repository: FactoryRepository,
    notes: str = "",
) -> CurriculumReleaseBundle:
    issues = validate_network(network, request, catalog, evidence)
    errors = [issue for issue in issues if issue.severity == IssueSeverity.ERROR]
    if errors:
        details = "; ".join(f"{issue.code}: {issue.message}" for issue in errors)
        raise ValueError(f"curriculum network cannot be published: {details}")

    cited_source_ids = {
        citation.source_id
        for point in network.points
        for citation in point.citations
    }
    source_by_id = {source.id: source for source in catalog.sources}
    unverified = sorted(
        source_id
        for source_id in cited_source_ids
        if source_id not in source_by_id or not source_by_id[source_id].locally_verified
    )
    if unverified:
        raise ValueError(f"curriculum release uses unverified sources: {unverified}")

    manifest = CurriculumReleaseManifest(
        release_id=f"curriculum-release-{uuid4().hex}",
        version=version,
        request_id=request.id,
        source_catalog_digest=stable_digest(catalog),
        evidence_digest=stable_digest(evidence),
        network_digest=stable_digest(network),
        notes=notes,
    )
    bundle = CurriculumReleaseBundle(manifest=manifest, network=network)
    repository.save_curriculum_release(bundle)
    return bundle
