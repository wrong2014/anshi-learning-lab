from learning_problem_factory.compiler import compile_diagnostic_probes


def test_compiler_builds_traceable_probe(valid_artifact) -> None:
    probes = compile_diagnostic_probes([valid_artifact])
    assert len(probes) == 1
    assert probes[0].learning_block_id == valid_artifact.learning_blocks[0].id
    assert probes[0].node_id == valid_artifact.nodes[0].id
    assert probes[0].source_citations[0].source_id == "source-math-demo-01"
    assert len(probes[0].options) == 2


def test_compiler_allows_model_distilled_probe_without_citations(distilled_artifact) -> None:
    probes = compile_diagnostic_probes([distilled_artifact])
    assert len(probes) == 1
    assert probes[0].source_citations == []
