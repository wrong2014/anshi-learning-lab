from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .curriculum_models import (
    CurriculumKnowledgeNetwork,
    CurriculumEvidencePack,
    CurriculumOutline,
    CurriculumPipelineRequest,
    CurriculumSourceCatalog,
)
from .curriculum_pipeline import CurriculumPipeline
from .curriculum_preview import write_curriculum_preview
from .curriculum_release import publish_curriculum_network
from .curriculum_validators import validate_network
from .models import (
    CurriculumProviderSet,
    KnowledgeArtifact,
    ProductionOutcome,
    ProductionRequest,
    ProviderSet,
)
from .official_seed import build_official_seed
from .orchestrator import ProductionFactory, publish_outcome
from .providers import build_providers
from .recipes import get_recipe, list_recipes
from .repository import FactoryRepository
from .specialized_models import SpecializedProductionOutcome
from .specialized_pipeline import SpecializedMaterialFactory, publish_specialized_outcome
from .validators import has_errors, validate_artifact


def _read_model(path: str, model_type):
    return model_type.model_validate_json(Path(path).read_text(encoding="utf-8-sig"))


def _write_model(path: Path, model) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Learning problem library production factory")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list-recipes", help="list available production recipes")

    run_parser = subparsers.add_parser("run", help="run a production request")
    run_parser.add_argument("--request", required=True)
    run_parser.add_argument("--providers", required=True)
    run_parser.add_argument("--database", default="artifacts/factory.db")
    run_parser.add_argument("--output-dir", default="artifacts/runs")

    validate_parser = subparsers.add_parser("validate-artifact", help="validate an artifact against a request")
    validate_parser.add_argument("--request", required=True)
    validate_parser.add_argument("--artifact", required=True)

    seed_parser = subparsers.add_parser(
        "build-curriculum-seed",
        help="build the deterministic official curriculum task-tree seed",
    )
    seed_parser.add_argument("--request", required=True)
    seed_parser.add_argument("--catalog", required=True)
    seed_parser.add_argument("--output", required=True)

    curriculum_parser = subparsers.add_parser(
        "run-curriculum",
        help="run outline, knowledge-point and graph agents in sequence",
    )
    curriculum_parser.add_argument("--request", required=True)
    curriculum_parser.add_argument("--catalog", required=True)
    curriculum_parser.add_argument("--seed", required=True)
    curriculum_parser.add_argument("--evidence", required=True)
    curriculum_parser.add_argument("--providers", required=True)
    curriculum_parser.add_argument("--output", required=True)
    curriculum_parser.add_argument("--checkpoint-dir", default="artifacts/checkpoints")
    curriculum_parser.add_argument("--database", default="artifacts/factory.db")

    validate_curriculum_parser = subparsers.add_parser(
        "validate-curriculum",
        help="validate curriculum coverage and graph integrity",
    )
    validate_curriculum_parser.add_argument("--request", required=True)
    validate_curriculum_parser.add_argument("--catalog", required=True)
    validate_curriculum_parser.add_argument("--network", required=True)
    validate_curriculum_parser.add_argument("--evidence", required=True)

    preview_curriculum_parser = subparsers.add_parser(
        "preview-curriculum",
        help="render a local HTML preview of the curriculum task tree",
    )
    preview_curriculum_parser.add_argument("--outline", required=True)
    preview_curriculum_parser.add_argument("--catalog", required=True)
    preview_curriculum_parser.add_argument("--evidence", required=True)
    preview_curriculum_parser.add_argument("--output", required=True)

    publish_curriculum_parser = subparsers.add_parser(
        "publish-curriculum",
        help="publish a validated curriculum knowledge network",
    )
    publish_curriculum_parser.add_argument("--request", required=True)
    publish_curriculum_parser.add_argument("--catalog", required=True)
    publish_curriculum_parser.add_argument("--evidence", required=True)
    publish_curriculum_parser.add_argument("--network", required=True)
    publish_curriculum_parser.add_argument("--version", required=True)
    publish_curriculum_parser.add_argument("--database", default="artifacts/factory.db")
    publish_curriculum_parser.add_argument("--output-dir", default="artifacts/releases")
    publish_curriculum_parser.add_argument("--notes", default="")

    specialized_parser = subparsers.add_parser(
        "run-specialized",
        help="run a core-thinking or psychology/cognition production request",
    )
    specialized_parser.add_argument("--request", required=True)
    specialized_parser.add_argument("--providers", required=True)
    specialized_parser.add_argument("--database", default="artifacts/factory.db")
    specialized_parser.add_argument("--output-dir", default="artifacts/runs")

    publish_specialized_parser = subparsers.add_parser(
        "publish-specialized",
        help="publish a completed core-thinking or psychology/cognition run",
    )
    publish_specialized_parser.add_argument("--outcome", required=True)
    publish_specialized_parser.add_argument("--version", required=True)
    publish_specialized_parser.add_argument("--database", default="artifacts/factory.db")
    publish_specialized_parser.add_argument("--output-dir", default="artifacts/releases")
    publish_specialized_parser.add_argument("--approved-by")
    publish_specialized_parser.add_argument("--notes", default="")

    publish_parser = subparsers.add_parser("publish", help="publish a completed run as an immutable release")
    publish_parser.add_argument("--outcome", required=True)
    publish_parser.add_argument("--version", required=True)
    publish_parser.add_argument("--database", default="artifacts/factory.db")
    publish_parser.add_argument("--output-dir", default="artifacts/releases")
    publish_parser.add_argument("--approved-by")
    publish_parser.add_argument("--notes", default="")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.command == "list-recipes":
        for recipe in list_recipes():
            risk = " [human approval required]" if recipe.requires_human_approval else ""
            print(f"{recipe.id}: {recipe.name}{risk}")
        return 0

    if args.command == "validate-artifact":
        request = _read_model(args.request, ProductionRequest)
        artifact = _read_model(args.artifact, KnowledgeArtifact)
        issues = validate_artifact(artifact, request)
        for issue in issues:
            print(f"{issue.severity.value}: {issue.code}: {issue.message}")
        return 1 if has_errors(issues) else 0

    if args.command == "build-curriculum-seed":
        request = _read_model(args.request, CurriculumPipelineRequest)
        catalog = _read_model(args.catalog, CurriculumSourceCatalog)
        seed = build_official_seed(request, catalog)
        _write_model(Path(args.output), seed)
        print(Path(args.output).resolve())
        return 0

    if args.command == "run-curriculum":
        request = _read_model(args.request, CurriculumPipelineRequest)
        catalog = _read_model(args.catalog, CurriculumSourceCatalog)
        seed = _read_model(args.seed, CurriculumOutline)
        evidence = _read_model(args.evidence, CurriculumEvidencePack)
        provider_set = _read_model(args.providers, CurriculumProviderSet)
        provider_map = build_providers(provider_set.providers)
        pipeline = CurriculumPipeline(
            outline_agents=[provider_map[item.name] for item in provider_set.by_role("outline")],
            knowledge_point_agents=[
                provider_map[item.name] for item in provider_set.by_role("knowledge_point")
            ],
            graph_agents=[provider_map[item.name] for item in provider_set.by_role("graph")],
            supervisor=provider_map[provider_set.by_role("supervisor")[0].name],
            checkpoint_dir=Path(args.checkpoint_dir) / request.id,
            repository=FactoryRepository(args.database),
        )
        network = pipeline.run(request, catalog, seed, evidence)
        _write_model(Path(args.output), network)
        print(Path(args.output).resolve())
        return 0

    if args.command == "validate-curriculum":
        request = _read_model(args.request, CurriculumPipelineRequest)
        catalog = _read_model(args.catalog, CurriculumSourceCatalog)
        network = _read_model(args.network, CurriculumKnowledgeNetwork)
        evidence = _read_model(args.evidence, CurriculumEvidencePack)
        issues = validate_network(network, request, catalog, evidence)
        for issue in issues:
            print(f"{issue.severity.value}: {issue.code}: {issue.message}")
        return 1 if has_errors(issues) else 0

    if args.command == "preview-curriculum":
        outline = _read_model(args.outline, CurriculumOutline)
        catalog = _read_model(args.catalog, CurriculumSourceCatalog)
        evidence = _read_model(args.evidence, CurriculumEvidencePack)
        target = write_curriculum_preview(outline, catalog, evidence, args.output)
        print(target.resolve())
        return 0

    if args.command == "publish-curriculum":
        request = _read_model(args.request, CurriculumPipelineRequest)
        catalog = _read_model(args.catalog, CurriculumSourceCatalog)
        evidence = _read_model(args.evidence, CurriculumEvidencePack)
        network = _read_model(args.network, CurriculumKnowledgeNetwork)
        bundle = publish_curriculum_network(
            network,
            request=request,
            catalog=catalog,
            evidence=evidence,
            version=args.version,
            repository=FactoryRepository(args.database),
            notes=args.notes,
        )
        target = Path(args.output_dir) / f"curriculum-{args.version}.json"
        if target.exists():
            raise FileExistsError(f"release file already exists and will not be overwritten: {target}")
        _write_model(target, bundle)
        print(target.resolve())
        return 0

    if args.command == "run-specialized":
        request = _read_model(args.request, ProductionRequest)
        provider_set = _read_model(args.providers, ProviderSet)
        recipe = get_recipe(request.recipe_id)
        provider_map = build_providers(provider_set.providers)
        factory = SpecializedMaterialFactory(
            planner=provider_map[provider_set.by_role("planner")[0].name],
            executors=[provider_map[item.name] for item in provider_set.by_role("executor")],
            supervisor=provider_map[provider_set.by_role("supervisor")[0].name],
            recipe=recipe,
            repository=FactoryRepository(args.database),
        )
        outcome = factory.run(request)
        target = Path(args.output_dir) / f"{outcome.run.id}.json"
        _write_model(target, outcome)
        print(target.resolve())
        return 0 if outcome.run.status == "completed" else 2

    if args.command == "publish-specialized":
        outcome = _read_model(args.outcome, SpecializedProductionOutcome)
        recipe = get_recipe(outcome.run.request.recipe_id)
        bundle = publish_specialized_outcome(
            outcome,
            recipe=recipe,
            version=args.version,
            repository=FactoryRepository(args.database),
            approved_by=args.approved_by,
            notes=args.notes,
        )
        target = Path(args.output_dir) / f"specialized-{args.version}.json"
        if target.exists():
            raise FileExistsError(f"release file already exists and will not be overwritten: {target}")
        _write_model(target, bundle)
        print(target.resolve())
        return 0

    if args.command == "run":
        request = _read_model(args.request, ProductionRequest)
        provider_set = _read_model(args.providers, ProviderSet)
        recipe = get_recipe(request.recipe_id)
        provider_map = build_providers(provider_set.providers)
        planner_config = provider_set.by_role("planner")[0]
        supervisor_config = provider_set.by_role("supervisor")[0]
        factory = ProductionFactory(
            planner=provider_map[planner_config.name],
            executors=[provider_map[item.name] for item in provider_set.by_role("executor")],
            supervisor=provider_map[supervisor_config.name],
            recipe=recipe,
            repository=FactoryRepository(args.database),
        )
        outcome = factory.run(request)
        target = Path(args.output_dir) / f"{outcome.run.id}.json"
        _write_model(target, outcome)
        print(target.resolve())
        return 0 if outcome.run.status == "completed" else 2

    if args.command == "publish":
        outcome = _read_model(args.outcome, ProductionOutcome)
        recipe = get_recipe(outcome.run.request.recipe_id)
        repository = FactoryRepository(args.database)
        bundle = publish_outcome(
            outcome,
            recipe=recipe,
            version=args.version,
            repository=repository,
            approved_by=args.approved_by,
            notes=args.notes,
        )
        target = Path(args.output_dir) / f"{args.version}.json"
        if target.exists():
            raise FileExistsError(f"release file already exists and will not be overwritten: {target}")
        _write_model(target, bundle)
        print(target.resolve())
        return 0

    return 1


if __name__ == "__main__":
    sys.exit(main())
