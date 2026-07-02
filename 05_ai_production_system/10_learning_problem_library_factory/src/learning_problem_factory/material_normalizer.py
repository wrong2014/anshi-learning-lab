from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

from .retrieval_models import (
    CorpusManifest,
    NormalizedCorpus,
    RetrievalEdge,
    RetrievalUnit,
)


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_name(path: Path) -> str:
    return path.as_posix()


def _flatten(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, bool):
        return ["是" if value else "否"]
    if isinstance(value, (int, float)):
        return [str(value)]
    if isinstance(value, list):
        result: list[str] = []
        for item in value:
            result.extend(_flatten(item))
        return result
    if isinstance(value, dict):
        result = []
        for key, item in value.items():
            flattened = "；".join(_flatten(item))
            if flattened:
                result.append(f"{key}：{flattened}")
        return result
    return [str(value)]


def _core_artifacts(data: dict[str, Any]) -> Iterable[tuple[str, int, dict[str, Any]]]:
    for subject, subject_bundle in data.get("subjects", {}).items():
        for artifact_index, artifact in enumerate(subject_bundle.get("artifacts", [])):
            yield subject, artifact_index, artifact


def _psychology_artifacts(data: dict[str, Any]) -> Iterable[tuple[int, dict[str, Any]]]:
    for artifact_index, artifact in enumerate(data.get("artifacts", [])):
        yield artifact_index, artifact


def normalize_materials(
    knowledge_path: str | Path,
    core_thinking_path: str | Path,
    psychology_path: str | Path,
) -> NormalizedCorpus:
    knowledge_path = Path(knowledge_path)
    core_thinking_path = Path(core_thinking_path)
    psychology_path = Path(psychology_path)

    knowledge = _load(knowledge_path)
    core = _load(core_thinking_path)
    psychology = _load(psychology_path)

    units: list[RetrievalUnit] = []
    edges: list[RetrievalEdge] = []
    warnings: list[str] = []

    knowledge_version, knowledge_units, knowledge_edges = _normalize_knowledge(
        knowledge, _artifact_name(knowledge_path)
    )
    units.extend(knowledge_units)
    edges.extend(knowledge_edges)

    core_version, core_units, core_edges = _normalize_core(
        core, _artifact_name(core_thinking_path)
    )
    units.extend(core_units)
    edges.extend(core_edges)

    psychology_version, psychology_units, psychology_edges = _normalize_psychology(
        psychology, _artifact_name(psychology_path)
    )
    units.extend(psychology_units)
    edges.extend(psychology_edges)

    if not any(unit.unit_type == "knowledge_point_observable_signal" for unit in units):
        warnings.append(
            "第一层正式知识图谱不含知识点级可观察卡点信号；不能把知识内容召回冒充诊断证据。"
        )

    ids = [unit.unit_id for unit in units]
    duplicates = [item for item, count in Counter(ids).items() if count > 1]
    if duplicates:
        raise ValueError(f"duplicate retrieval unit ids: {duplicates[:5]}")

    unit_counts = dict(Counter(unit.layer for unit in units))
    edge_counts = dict(Counter(edge.layer for edge in edges))
    return NormalizedCorpus(
        manifest=CorpusManifest(
            source_digests={
                "knowledge_graph": _digest(knowledge_path),
                "core_thinking": _digest(core_thinking_path),
                "psychology_cognition": _digest(psychology_path),
            },
            source_versions={
                "knowledge_graph": knowledge_version,
                "core_thinking": core_version,
                "psychology_cognition": psychology_version,
            },
            unit_counts=unit_counts,
            edge_counts=edge_counts,
            warnings=warnings,
        ),
        units=units,
        edges=edges,
    )


def _normalize_knowledge(
    data: dict[str, Any], source_artifact: str
) -> tuple[str, list[RetrievalUnit], list[RetrievalEdge]]:
    manifest = data.get("manifest", {})
    network = data.get("network", data)
    version = str(manifest.get("version") or manifest.get("release_id") or network.get("schema_version", "unknown"))
    units: list[RetrievalUnit] = []

    for index, point in enumerate(network.get("points", [])):
        point_id = point["id"]
        profile_text = "；".join(_flatten(point.get("subject_profile", {})))
        aliases = "、".join(point.get("aliases", []))
        text_parts = [
            f"知识点：{point['name']}",
            f"定义：{point['definition']}",
            f"学习要求：{point['learning_expectation']}",
            f"核心思维：{'、'.join(point.get('core_thinking', []))}",
            f"学科画像：{profile_text}",
        ]
        if aliases:
            text_parts.append(f"别名：{aliases}")
        units.append(
            RetrievalUnit(
                unit_id=f"kg::{point_id}::overview",
                layer="knowledge_graph",
                unit_type="knowledge_point_overview",
                source_id=point_id,
                parent_id=point_id,
                source_artifact=source_artifact,
                source_path=f"network.points[{index}]" if "network" in data else f"points[{index}]",
                material_version=version,
                approval_scope="published",
                title=point["name"],
                text="\n".join(text_parts),
                subject=point["subject"],
                grade_min=point["grade_min"],
                grade_max=point["grade_max"],
                citations=point.get("citations", []),
                metadata={
                    "outline_node_id": point.get("outline_node_id"),
                    "concept_kind": point.get("concept_kind"),
                    "aliases": point.get("aliases", []),
                },
            )
        )

    edges = [
        RetrievalEdge(
            source_id=relation["source_point_id"],
            target_id=relation["target_point_id"],
            relation_type=relation["relation_type"],
            rationale=relation.get("rationale", ""),
            layer="knowledge_graph",
            source_artifact=source_artifact,
            source_path=(
                f"network.relations[{index}]" if "network" in data else f"relations[{index}]"
            ),
        )
        for index, relation in enumerate(network.get("relations", []))
    ]
    return version, units, edges


def _normalize_core(
    data: dict[str, Any], source_artifact: str
) -> tuple[str, list[RetrievalUnit], list[RetrievalEdge]]:
    version = str(data.get("bundle_id") or data.get("schema_version", "unknown"))
    units: list[RetrievalUnit] = []
    edges: list[RetrievalEdge] = []

    for subject, artifact_index, artifact in _core_artifacts(data):
        for dimension_index, dimension in enumerate(artifact.get("dimensions", [])):
            dimension_id = dimension["id"]
            base_path = f"subjects.{subject}.artifacts[{artifact_index}].dimensions[{dimension_index}]"
            profile = "；".join(_flatten(dimension.get("profile", {})))
            units.append(
                RetrievalUnit(
                    unit_id=f"core::{dimension_id}::overview",
                    layer="core_thinking",
                    unit_type="thinking_dimension_overview",
                    source_id=dimension_id,
                    parent_id=dimension_id,
                    source_artifact=source_artifact,
                    source_path=base_path,
                    material_version=version,
                    approval_scope="internal_conditionally_approved",
                    title=dimension["name"],
                    text=(
                        f"核心思维：{dimension['name']}\n"
                        f"学术定义：{dimension['academic_definition']}\n"
                        f"通俗本质：{dimension['plain_essence']}\n"
                        f"学科表现：{profile}\n"
                        f"发展路径：{'；'.join(dimension.get('development_path', []))}"
                    ),
                    subject=dimension.get("subject", subject),
                    grade_min=1,
                    grade_max=9,
                    citations=dimension.get("citations", []),
                    metadata={"depends_on": dimension.get("depends_on", []), "supports": dimension.get("supports", [])},
                )
            )

            for signal_index, signal in enumerate(dimension.get("observable_deficits", [])):
                observer = signal.get("observer")
                units.append(
                    RetrievalUnit(
                        unit_id=f"core::{dimension_id}::signal::{signal_index}",
                        layer="core_thinking",
                        unit_type="thinking_observable_signal",
                        source_id=f"{dimension_id}.signal.{signal_index}",
                        parent_id=dimension_id,
                        source_artifact=source_artifact,
                        source_path=f"{base_path}.observable_deficits[{signal_index}]",
                        material_version=version,
                        approval_scope="internal_conditionally_approved",
                        title=f"{dimension['name']}：{observer}可观察表现",
                        text=(
                            f"可观察行为：{signal['behavior']}\n"
                            f"发生场景：{signal['context']}\n"
                            f"可能断点：{signal['likely_breakpoint']}"
                        ),
                        subject=dimension.get("subject", subject),
                        grade_min=1,
                        grade_max=9,
                        actor=observer,
                        citations=dimension.get("citations", []),
                    )
                )

            for stage_index, stage in enumerate(dimension.get("stage_features", [])):
                units.append(
                    RetrievalUnit(
                        unit_id=f"core::{dimension_id}::stage::{stage_index}",
                        layer="core_thinking",
                        unit_type="thinking_stage_feature",
                        source_id=f"{dimension_id}.stage.{stage_index}",
                        parent_id=dimension_id,
                        source_artifact=source_artifact,
                        source_path=f"{base_path}.stage_features[{stage_index}]",
                        material_version=version,
                        approval_scope="internal_conditionally_approved",
                        title=f"{dimension['name']}：{stage['grade_min']}-{stage['grade_max']}年级",
                        text=f"学段要求：{stage['expectation']}\n典型过渡：{stage['typical_transition']}",
                        subject=dimension.get("subject", subject),
                        grade_min=stage["grade_min"],
                        grade_max=stage["grade_max"],
                        citations=dimension.get("citations", []),
                    )
                )

            for relation_type, targets in (
                ("depends_on", dimension.get("depends_on", [])),
                ("supports", dimension.get("supports", [])),
            ):
                for target_index, target in enumerate(targets):
                    source_id, target_id = (
                        (target, dimension_id) if relation_type == "depends_on" else (dimension_id, target)
                    )
                    edges.append(
                        RetrievalEdge(
                            source_id=source_id,
                            target_id=target_id,
                            relation_type=relation_type,
                            layer="core_thinking",
                            source_artifact=source_artifact,
                            source_path=f"{base_path}.{relation_type}[{target_index}]",
                        )
                    )
    return version, units, edges


def _normalize_psychology(
    data: dict[str, Any], source_artifact: str
) -> tuple[str, list[RetrievalUnit], list[RetrievalEdge]]:
    version = str(data.get("bundle_id") or data.get("schema_version", "unknown"))
    units: list[RetrievalUnit] = []
    edges: list[RetrievalEdge] = []

    for artifact_index, artifact in _psychology_artifacts(data):
        for dimension_index, dimension in enumerate(artifact.get("dimensions", [])):
            dimension_id = dimension["id"]
            base_path = f"artifacts[{artifact_index}].dimensions[{dimension_index}]"
            citations = dimension.get("citations", []) + dimension.get("theory_citations", [])
            units.append(
                RetrievalUnit(
                    unit_id=f"psy::{dimension_id}::overview",
                    layer="psychology_cognition",
                    unit_type="psychology_dimension_overview",
                    source_id=dimension_id,
                    parent_id=dimension_id,
                    source_artifact=source_artifact,
                    source_path=base_path,
                    material_version=version,
                    approval_scope="internal_conditionally_approved",
                    safety_level="sensitive",
                    title=dimension["name"],
                    text=(
                        f"维度：{dimension['name']}\n理论：{dimension['theory_name']}\n"
                        f"学术定义：{dimension['academic_definition']}\n"
                        f"与学习表现的非确定关联：{dimension['achievement_mechanism']}"
                    ),
                    grade_min=1,
                    grade_max=9,
                    citations=citations,
                    metadata={"dimension_layer": dimension.get("layer")},
                )
            )

            for scenario_index, scenario in enumerate(dimension.get("subject_scenarios", [])):
                units.append(
                    RetrievalUnit(
                        unit_id=f"psy::{dimension_id}::scenario::{scenario_index}",
                        layer="psychology_cognition",
                        unit_type="psychology_subject_scenario",
                        source_id=f"{dimension_id}.scenario.{scenario_index}",
                        parent_id=dimension_id,
                        source_artifact=source_artifact,
                        source_path=f"{base_path}.subject_scenarios[{scenario_index}]",
                        material_version=version,
                        approval_scope="internal_conditionally_approved",
                        safety_level="sensitive",
                        title=f"{dimension['name']}：{scenario['subject']}学习场景",
                        text=scenario["manifestation"],
                        subject=scenario["subject"],
                        grade_min=1,
                        grade_max=9,
                        citations=citations,
                    )
                )

            for actor, field in (("parent", "parent_signals"), ("learner", "learner_signals")):
                for signal_index, signal in enumerate(dimension.get(field, [])):
                    units.append(
                        RetrievalUnit(
                            unit_id=f"psy::{dimension_id}::{actor}-signal::{signal_index}",
                            layer="psychology_cognition",
                            unit_type="psychology_observable_signal",
                            source_id=f"{dimension_id}.{actor}-signal.{signal_index}",
                            parent_id=dimension_id,
                            source_artifact=source_artifact,
                            source_path=f"{base_path}.{field}[{signal_index}]",
                            material_version=version,
                            approval_scope="internal_conditionally_approved",
                            safety_level="sensitive",
                            title=f"{dimension['name']}：{actor}信号",
                            text=signal,
                            grade_min=1,
                            grade_max=9,
                            actor=actor,
                            citations=citations,
                        )
                    )

            for support_index, support in enumerate(dimension.get("ai_support_scope", [])):
                units.append(
                    RetrievalUnit(
                        unit_id=f"psy::{dimension_id}::support::{support_index}",
                        layer="psychology_cognition",
                        unit_type="low_risk_ai_support",
                        source_id=f"{dimension_id}.support.{support_index}",
                        parent_id=dimension_id,
                        source_artifact=source_artifact,
                        source_path=f"{base_path}.ai_support_scope[{support_index}]",
                        material_version=version,
                        approval_scope="internal_conditionally_approved",
                        safety_level="sensitive",
                        title=f"{dimension['name']}：低风险学习支持",
                        text=support,
                        grade_min=1,
                        grade_max=9,
                        actor="system",
                        citations=citations,
                    )
                )

            severity = dimension.get("severity", {})
            for severity_key, safety_level in (
                ("normal_range", "sensitive"),
                ("support_needed", "sensitive"),
                ("professional_help", "referral"),
            ):
                if severity.get(severity_key):
                    units.append(
                        RetrievalUnit(
                            unit_id=f"psy::{dimension_id}::severity::{severity_key}",
                            layer="psychology_cognition",
                            unit_type="psychology_severity_boundary",
                            source_id=f"{dimension_id}.severity.{severity_key}",
                            parent_id=dimension_id,
                            source_artifact=source_artifact,
                            source_path=f"{base_path}.severity.{severity_key}",
                            material_version=version,
                            approval_scope="internal_conditionally_approved",
                            safety_level=safety_level,
                            title=f"{dimension['name']}：{severity_key}",
                            text=severity[severity_key],
                            grade_min=1,
                            grade_max=9,
                            actor="system",
                            citations=citations,
                        )
                    )

            for referral_index, referral in enumerate(dimension.get("referral_conditions", [])):
                units.append(
                    RetrievalUnit(
                        unit_id=f"psy::{dimension_id}::referral::{referral_index}",
                        layer="psychology_cognition",
                        unit_type="professional_referral_condition",
                        source_id=f"{dimension_id}.referral.{referral_index}",
                        parent_id=dimension_id,
                        source_artifact=source_artifact,
                        source_path=f"{base_path}.referral_conditions[{referral_index}]",
                        material_version=version,
                        approval_scope="internal_conditionally_approved",
                        safety_level="referral",
                        title=f"{dimension['name']}：专业转介条件",
                        text=referral,
                        grade_min=1,
                        grade_max=9,
                        actor="system",
                        citations=citations,
                    )
                )

            for relation_type, targets in (
                ("may_lead_to", dimension.get("may_lead_to", [])),
                ("may_be_caused_by", dimension.get("may_be_caused_by", [])),
            ):
                for target_index, target in enumerate(targets):
                    source_id, target_id = (
                        (target, dimension_id)
                        if relation_type == "may_be_caused_by"
                        else (dimension_id, target)
                    )
                    edges.append(
                        RetrievalEdge(
                            source_id=source_id,
                            target_id=target_id,
                            relation_type=relation_type,
                            rationale="待验证的关联假设，不表示个体因果关系。",
                            layer="psychology_cognition",
                            source_artifact=source_artifact,
                            source_path=f"{base_path}.{relation_type}[{target_index}]",
                        )
                    )
    return version, units, edges
