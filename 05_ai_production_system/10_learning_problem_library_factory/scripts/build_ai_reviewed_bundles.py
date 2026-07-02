from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from learning_problem_factory.models import ProductionRequest
from learning_problem_factory.recipes import get_recipe
from learning_problem_factory.specialized_pipeline import ARTIFACT_ADAPTER
from learning_problem_factory.specialized_validators import validate_specialized_artifact


ROOT = Path(__file__).resolve().parents[1]


PSYCHOLOGY_SOURCE_REVIEW = {
    "theory-self-efficacy-bandura-1977": "题名、作者、1977年卷页与DOI一致；效能预期影响启动、努力和坚持的摘要主张一致。",
    "theory-learned-helplessness-update-2016": "PubMed/PMC元数据与原作者修订一致；来源卡保留了不能简单沿用早期解释的关键限制。",
    "theory-clinical-perfectionism-shafran-2002": "ScienceDirect题名、作者、DOI和核心定义一致；工作包明确不把该构念作为诊断。",
    "theory-test-anxiety-adolescents-torrano-2020": "Frontiers原始研究、DOI与青少年多系统考试焦虑框架一致。",
    "theory-school-burnout-salmela-aro-2009": "期刊/大学研究门户元数据一致；耗竭、疏离、学生不足感三维结构与论文一致。",
    "theory-cognitive-load-sweller-1988": "Cognitive Science题名、DOI及有限加工资源/元素交互主张一致；已删除超出本来源的三分法。",
    "theory-working-memory-baddeley-2000": "PubMed元数据与摘要一致；情景缓冲器为有限容量、多模态整合组件。",
    "theory-attentional-control-eysenck-2007": "APA DOI、作者和注意控制理论主张一致；工作包明确不据此诊断ADHD。",
    "theory-metacognition-flavell-1979": "题名、卷页、DOI与元认知知识/体验/监控框架一致。",
    "theory-intrinsic-extrinsic-ryan-deci-2000": "PubMed及作者公开论文元数据一致；外在动机自主程度连续体的表述一致。",
    "theory-achievement-goals-elliot-mcgregor-2001": "PubMed及论文PDF元数据一致；2×2四类目标框架一致，已把结果机制改为非确定关联。",
    "theory-self-determination-ryan-deci-2000": "PubMed及作者公开论文元数据一致；自主、胜任、关系三需要主张一致。",
    "guideline-who-adolescent-mental-health-2025": "WHO权威页面可访问；早期识别、避免过度医疗化和获得适当照护的边界一致。",
    "guideline-unicef-teen-support-referral": "UNICEF权威页面可访问；持续数周并影响功能、对自己或他人有危险时求助的边界一致。",
    "guideline-nimh-child-adolescent-warning-signs": "NIMH权威页面可访问；持续功能受损、自伤/自杀等预警与专业求助边界一致。",
}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def review_core_thinking() -> tuple[Path, list[dict], dict]:
    source_path = ROOT / "artifacts/core-thinking/core-thinking-k9-v1.0.0-draft.json"
    bundle = json.loads(source_path.read_text(encoding="utf-8"))
    corrections: list[dict] = []

    for artifact in bundle["subjects"]["math"]["artifacts"]:
        for dimension in artifact["dimensions"]:
            if dimension["id"] != "math.math-language-model":
                continue
            removed = [
                citation
                for citation in dimension["citations"]
                if citation["source_id"] == "moe-math-2022-progression-page-93"
            ]
            dimension["citations"] = [
                citation
                for citation in dimension["citations"]
                if citation["source_id"] != "moe-math-2022-progression-page-93"
            ]
            corrections.append(
                {
                    "artifact": dimension["id"],
                    "code": "remove_unsupported_page_93_model_claim",
                    "before": removed,
                    "after": dimension["citations"],
                    "basis": "数学课标逻辑页93举例支持数学抽象与逻辑推理进阶，未直接支持模型意识/模型观念。",
                }
            )

    for artifact in bundle["subjects"]["physics"]["artifacts"]:
        for dimension in artifact["dimensions"]:
            if dimension["id"] != "physics.scientific_argumentation":
                continue
            before = {
                "academic_definition": dimension["academic_definition"],
                "citations": dimension["citations"],
            }
            dimension["academic_definition"] = (
                "科学论证是在研究问题中基于事实证据进行分析和解释，并使用证据表达、"
                "支持或检验观点与结论的能力。"
            )
            dimension["citations"] = [
                {
                    "source_id": "moe-physics-2022-thinking-pages-4-6",
                    "locator": "逻辑页 6",
                    "claim": (
                        "有利用证据对所研究的问题进行分析和解释的意识，能使用简单和直接的"
                        "证据表达自己的观点，具有初步的科学论证能力。"
                    ),
                },
                {
                    "source_id": "moe-physics-2022-quality-pages-39-40",
                    "locator": "逻辑页 40",
                    "claim": "能依照证据形成自己的看法，具有利用证据进行论证的意识。",
                },
            ]
            corrections.append(
                {
                    "artifact": dimension["id"],
                    "code": "separate_argumentation_from_questioning_innovation",
                    "before": before,
                    "after": {
                        "academic_definition": dimension["academic_definition"],
                        "citations": dimension["citations"],
                    },
                    "basis": "物理课标逻辑页6和40分别给出科学论证的可观察表现；原定义误用了质疑创新表述。",
                }
            )

    for artifact in bundle["subjects"]["chemistry"]["artifacts"]:
        for dimension in artifact["dimensions"]:
            if dimension["id"] != "chemistry.questioning_innovation":
                continue
            before = {
                "academic_definition": dimension["academic_definition"],
                "citations": dimension["citations"],
                "source_ids": artifact["source_ids"],
            }
            dimension["academic_definition"] = (
                "质疑创新是在化学学习中基于事实与逻辑，对不同信息、观点和结论进行质疑"
                "与批判，并在检验和修正的基础上提出创造性见解的科学思维能力。"
            )
            dimension["citations"] = [
                {
                    "source_id": "moe-chemistry-2022-thinking-pages-5-7",
                    "locator": "逻辑页 6",
                    "claim": (
                        "科学思维包括基于事实与逻辑进行独立思考和判断，对不同信息、观点和"
                        "结论进行质疑与批判，提出创造性见解的能力。"
                    ),
                },
                *dimension["citations"],
            ]
            artifact["source_ids"] = sorted(
                set(artifact["source_ids"])
                | {"moe-chemistry-2022-thinking-pages-5-7"}
            )
            corrections.append(
                {
                    "artifact": dimension["id"],
                    "code": "classify_questioning_innovation_as_scientific_thinking",
                    "before": before,
                    "after": {
                        "academic_definition": dimension["academic_definition"],
                        "citations": dimension["citations"],
                        "source_ids": artifact["source_ids"],
                    },
                    "basis": "化学课标逻辑页6明确把质疑、批判和创新意识列入科学思维。",
                }
            )

    citation_checks = []
    validation_errors = []
    for subject, subject_payload in bundle["subjects"].items():
        request = ProductionRequest.model_validate_json(
            (ROOT / subject_payload["request_file"]).read_text(encoding="utf-8")
        )
        source_by_id = {source.id: source for source in request.source_pack.documents}
        recipe = get_recipe(request.recipe_id)
        for raw_artifact in subject_payload["artifacts"]:
            artifact = ARTIFACT_ADAPTER.validate_python(raw_artifact)
            issues = validate_specialized_artifact(artifact, request, recipe)
            validation_errors.extend(
                f"{artifact.batch_id}: {issue.code}: {issue.message}" for issue in issues
            )
            for dimension in artifact.dimensions:
                for citation in dimension.citations:
                    source = source_by_id[citation.source_id]
                    pages = [int(item) for item in re.findall(r"\d+", citation.locator)]
                    pages_present = all(
                        f"【逻辑页 {page}】" in source.content for page in pages
                    )
                    citation_checks.append(
                        {
                            "dimension_id": dimension.id,
                            "source_id": citation.source_id,
                            "locator": citation.locator,
                            "pages_present": pages_present,
                        }
                    )
                    if not pages_present:
                        validation_errors.append(
                            f"{dimension.id}: citation pages missing for {citation.locator}"
                        )

    reviewed_at = datetime.now(timezone.utc).isoformat()
    bundle["ai_review"] = {
        "reviewer": "Codex AI",
        "reviewed_at": reviewed_at,
        "decision": "conditionally_approved_for_internal_use",
        "public_release_approved": False,
        "scope": "结构化资料内部接入、测试和后续人工复核",
        "corrections": corrections,
        "citation_page_checks": {
            "total": len(citation_checks),
            "passed": sum(item["pages_present"] for item in citation_checks),
        },
        "validation_errors": validation_errors,
        "limitations": [
            "AI语义复核不能替代教育专家对课标解释的具名责任。",
            "未将任何来源的 verified_by_human 改为 true。",
        ],
    }
    output_path = ROOT / "artifacts/reviews/core-thinking-k9-v1.0.0-ai-reviewed.json"
    write_json(output_path, bundle)
    return output_path, corrections, {
        "citation_checks": citation_checks,
        "validation_errors": validation_errors,
    }


def review_psychology() -> tuple[Path, list[dict], dict]:
    source_path = ROOT / "artifacts/psychology/psychology-cognition-k9-v1.0.0-human-review.json"
    bundle = json.loads(source_path.read_text(encoding="utf-8"))
    corrections: list[dict] = []

    for artifact in bundle["artifacts"]:
        for dimension in artifact["dimensions"]:
            if dimension["id"] == "cognition.cognitive-load":
                before = dimension["academic_definition"]
                dimension["academic_definition"] = (
                    "认知负荷是学习或问题解决对有限工作记忆资源提出的加工要求。任务元素之间"
                    "的交互形成内在复杂性，呈现方式和求解活动还可能带来与图式建构无关的额外负担。"
                )
                corrections.append(
                    {
                        "artifact": dimension["id"],
                        "code": "limit_cognitive_load_definition_to_1988_source",
                        "before": before,
                        "after": dimension["academic_definition"],
                        "basis": "Sweller 1988支持有限加工资源、元素交互和额外负担；原文的三分法超出了当前来源卡。",
                    }
                )
            if dimension["id"] == "motivation.achievement-goals":
                before = dimension["achievement_mechanism"]
                dimension["achievement_mechanism"] = (
                    "不同成就目标取向可能伴随不同的任务选择、学习策略、努力方式和失败应对。"
                    "这些是情境化关联，不能用某一种目标取向直接预测个体成绩、焦虑或人格。"
                )
                corrections.append(
                    {
                        "artifact": dimension["id"],
                        "code": "soften_achievement_goal_causal_claim",
                        "before": before,
                        "after": dimension["achievement_mechanism"],
                        "basis": "Elliot与McGregor 2001支持2×2分类；工作包应避免把群体关联写成个体确定因果。",
                    }
                )

    request = ProductionRequest.model_validate_json(
        (ROOT / bundle["request_file"]).read_text(encoding="utf-8")
    )
    recipe = get_recipe(request.recipe_id)
    validation_errors = []
    source_ids = {source.id for source in request.source_pack.documents}
    missing_source_reviews = sorted(source_ids - set(PSYCHOLOGY_SOURCE_REVIEW))
    extra_source_reviews = sorted(set(PSYCHOLOGY_SOURCE_REVIEW) - source_ids)
    if missing_source_reviews or extra_source_reviews:
        validation_errors.append(
            "psychology source review coverage mismatch: "
            f"missing={missing_source_reviews}, extra={extra_source_reviews}"
        )
    dimension_ids = set()
    relation_targets = set()
    for raw_artifact in bundle["artifacts"]:
        artifact = ARTIFACT_ADAPTER.validate_python(raw_artifact)
        issues = validate_specialized_artifact(artifact, request, recipe)
        validation_errors.extend(
            f"{artifact.batch_id}: {issue.code}: {issue.message}" for issue in issues
        )
        for dimension in artifact.dimensions:
            dimension_ids.add(dimension.id)
            relation_targets.update(dimension.may_lead_to)
            relation_targets.update(dimension.may_be_caused_by)
    dangling = sorted(relation_targets - dimension_ids)
    if dangling:
        validation_errors.append(f"dangling psychology relations: {dangling}")

    reviewed_at = datetime.now(timezone.utc).isoformat()
    bundle["ai_review"] = {
        "reviewer": "Codex AI",
        "reviewed_at": reviewed_at,
        "decision": "conditionally_approved_for_internal_use",
        "public_release_approved": False,
        "scope": "内部接入、产品安全测试和专业人员后续逐条复核",
        "corrections": corrections,
        "source_reviews": [
            {
                "source_id": source.id,
                "locator": source.locator,
                "verified_by_codex_ai": True,
                "verified_by_human": source.verified_by_human,
                "review_note": PSYCHOLOGY_SOURCE_REVIEW[source.id],
            }
            for source in request.source_pack.documents
        ],
        "validation_errors": validation_errors,
        "limitations": [
            "本审核不是心理或医学专业执业意见。",
            "工作包仍须具名人类审批者签署后才能公开发布。",
            "未将任何来源的 verified_by_human 改为 true。",
        ],
    }
    output_path = ROOT / "artifacts/reviews/psychology-cognition-k9-v1.0.0-ai-reviewed.json"
    write_json(output_path, bundle)
    return output_path, corrections, {
        "validation_errors": validation_errors,
        "dimension_count": len(dimension_ids),
        "dangling_relations": dangling,
        "source_review_count": len(source_ids) - len(missing_source_reviews),
    }


def main() -> None:
    core_path, core_corrections, core_audit = review_core_thinking()
    psychology_path, psychology_corrections, psychology_audit = review_psychology()
    errors = core_audit["validation_errors"] + psychology_audit["validation_errors"]
    manifest = {
        "schema_version": "1.0",
        "review_id": "codex-ai-conditional-approval-2026-07-02",
        "reviewer": "Codex AI",
        "review_type": "ai_semantic_and_deterministic_review",
        "decision": "conditionally_approved_for_internal_use" if not errors else "rejected",
        "public_release_approved": False,
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "outputs": {
            "core_thinking": str(core_path.relative_to(ROOT)).replace("\\", "/"),
            "psychology_cognition": str(psychology_path.relative_to(ROOT)).replace("\\", "/"),
        },
        "output_sha256": {
            "core_thinking": digest(core_path),
            "psychology_cognition": digest(psychology_path),
        },
        "correction_count": len(core_corrections) + len(psychology_corrections),
        "core_thinking_corrections": core_corrections,
        "psychology_corrections": psychology_corrections,
        "checks": {
            "core_citation_pages": {
                "total": len(core_audit["citation_checks"]),
                "passed": sum(
                    item["pages_present"] for item in core_audit["citation_checks"]
                ),
            },
            "psychology_dimension_count": psychology_audit["dimension_count"],
            "psychology_source_reviews": psychology_audit["source_review_count"],
            "psychology_dangling_relations": psychology_audit["dangling_relations"],
            "validation_errors": errors,
        },
        "approval_scope": [
            "内部产品接入",
            "诊断问题编译器联调",
            "安全测试与人工复核准备",
        ],
        "excluded_scope": [
            "面向公众的心理评估或诊断",
            "替代教育心理或临床专业判断",
            "宣称已由人类专家核验",
        ],
    }
    manifest_path = ROOT / "artifacts/reviews/codex-ai-conditional-approval-2026-07-02.json"
    write_json(manifest_path, manifest)
    print(core_path.resolve())
    print(psychology_path.resolve())
    print(manifest_path.resolve())
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
