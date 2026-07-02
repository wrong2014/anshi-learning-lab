from __future__ import annotations

from .models import DiagnosticProbe, DiagnosticProbeOption, KnowledgeArtifact


def compile_diagnostic_probes(artifacts: list[KnowledgeArtifact]) -> list[DiagnosticProbe]:
    probes: list[DiagnosticProbe] = []
    seen_ids: set[str] = set()

    for artifact in artifacts:
        node_by_id = {node.id: node for node in artifact.nodes}
        for block in artifact.learning_blocks:
            node = node_by_id.get(block.node_id)
            if node is None:
                raise ValueError(f"cannot compile block {block.id}: node {block.node_id} does not exist")
            citations = list(node.citations)
            known_citations = {(item.source_id, item.locator, item.claim) for item in citations}
            for citation in block.citations:
                key = (citation.source_id, citation.locator, citation.claim)
                if key not in known_citations:
                    citations.append(citation)
                    known_citations.add(key)

            for index, blueprint in enumerate(block.probe_blueprints, start=1):
                probe_id = f"probe-{block.id}-{index:02d}"
                if probe_id in seen_ids:
                    raise ValueError(f"compiled probe id collision: {probe_id}")
                seen_ids.add(probe_id)
                probes.append(
                    DiagnosticProbe(
                        id=probe_id,
                        artifact_candidate_id=artifact.candidate_id,
                        subject=node.subject,
                        grade_min=node.grade_min,
                        grade_max=node.grade_max,
                        module=node.module,
                        node_id=node.id,
                        learning_block_id=block.id,
                        audience=blueprint.audience,
                        stem=blueprint.stem,
                        options=[DiagnosticProbeOption(**item.model_dump()) for item in blueprint.options],
                        evidence_needed=blueprint.evidence_needed,
                        source_citations=citations,
                    )
                )
    return probes
