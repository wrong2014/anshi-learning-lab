"""Learning problem library production factory."""

from .models import (
    KnowledgeArtifact,
    ProductionRequest,
    ReleaseBundle,
    SourcePack,
)
from .curriculum_models import (
    CurriculumKnowledgeNetwork,
    CurriculumOutline,
    CurriculumReleaseBundle,
)
from .curriculum_pipeline import CurriculumPipeline
from .curriculum_release import publish_curriculum_network
from .specialized_models import SpecializedProductionOutcome, SpecializedReleaseBundle
from .specialized_pipeline import SpecializedMaterialFactory, publish_specialized_outcome

__all__ = [
    "KnowledgeArtifact",
    "ProductionRequest",
    "ReleaseBundle",
    "SourcePack",
    "CurriculumKnowledgeNetwork",
    "CurriculumOutline",
    "CurriculumPipeline",
    "CurriculumReleaseBundle",
    "publish_curriculum_network",
    "SpecializedMaterialFactory",
    "SpecializedProductionOutcome",
    "SpecializedReleaseBundle",
    "publish_specialized_outcome",
]

__version__ = "0.2.0"
