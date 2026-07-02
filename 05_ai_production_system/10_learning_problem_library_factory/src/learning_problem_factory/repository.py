from __future__ import annotations

from pathlib import Path
import json
import sqlite3

from pydantic import BaseModel

from .curriculum_models import (
    CurriculumKnowledgeNetwork,
    CurriculumPipelineRequest,
    CurriculumReleaseBundle,
)

from .models import (
    KnowledgeArtifact,
    ProductionRun,
    ReleaseBundle,
    SupervisionReport,
    ValidationIssue,
    utc_now,
)
from .specialized_models import (
    SpecializedArtifact,
    SpecializedProductionRun,
    SpecializedReleaseBundle,
)


class FactoryRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path)
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialize(self) -> None:
        with self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    provider_name TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                CREATE TABLE IF NOT EXISTS reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES runs(id)
                );
                CREATE TABLE IF NOT EXISTS releases (
                    release_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL UNIQUE,
                    state TEXT NOT NULL,
                    bundle_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS curriculum_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    request_json TEXT NOT NULL,
                    network_json TEXT,
                    error TEXT,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS curriculum_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    provider_name TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES curriculum_runs(id)
                );
                CREATE TABLE IF NOT EXISTS curriculum_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES curriculum_runs(id)
                );
                CREATE TABLE IF NOT EXISTS curriculum_repairs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    stage TEXT NOT NULL,
                    unit_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    provider_name TEXT NOT NULL,
                    repairs_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES curriculum_runs(id)
                );
                CREATE TABLE IF NOT EXISTS curriculum_releases (
                    release_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL UNIQUE,
                    bundle_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS specialized_runs (
                    id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS specialized_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    provider_name TEXT NOT NULL,
                    candidate_id TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES specialized_runs(id)
                );
                CREATE TABLE IF NOT EXISTS specialized_reviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    run_id TEXT NOT NULL,
                    batch_id TEXT NOT NULL,
                    attempt_number INTEGER NOT NULL,
                    report_json TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(run_id) REFERENCES specialized_runs(id)
                );
                CREATE TABLE IF NOT EXISTS specialized_releases (
                    release_id TEXT PRIMARY KEY,
                    version TEXT NOT NULL UNIQUE,
                    bundle_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                );
                """
            )

    def save_run(self, run: ProductionRun) -> None:
        run.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO runs(id, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (run.id, run.status, run.model_dump_json(), run.updated_at.isoformat()),
            )

    def load_run(self, run_id: str) -> ProductionRun | None:
        with self._connect() as connection:
            row = connection.execute("SELECT payload_json FROM runs WHERE id = ?", (run_id,)).fetchone()
        return ProductionRun.model_validate_json(row[0]) if row else None

    def record_attempt(
        self,
        run_id: str,
        batch_id: str,
        attempt_number: int,
        artifact: KnowledgeArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        validation_json = "[" + ",".join(item.model_dump_json() for item in issues) + "]"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO attempts(
                    run_id, batch_id, attempt_number, provider_name, candidate_id,
                    artifact_json, validation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    batch_id,
                    attempt_number,
                    artifact.provider_name,
                    artifact.candidate_id,
                    artifact.model_dump_json(),
                    validation_json,
                    utc_now().isoformat(),
                ),
            )

    def record_review(
        self,
        run_id: str,
        batch_id: str,
        attempt_number: int,
        report: SupervisionReport,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO reviews(run_id, batch_id, attempt_number, report_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (run_id, batch_id, attempt_number, report.model_dump_json(), utc_now().isoformat()),
            )

    def save_release(self, bundle: ReleaseBundle) -> None:
        manifest = bundle.manifest
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO releases(release_id, version, state, bundle_json, created_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    manifest.release_id,
                    manifest.version,
                    manifest.state.value,
                    bundle.model_dump_json(),
                    manifest.created_at.isoformat(),
                ),
            )

    def load_release(self, version: str) -> ReleaseBundle | None:
        with self._connect() as connection:
            row = connection.execute("SELECT bundle_json FROM releases WHERE version = ?", (version,)).fetchone()
        return ReleaseBundle.model_validate_json(row[0]) if row else None

    def save_curriculum_run(
        self,
        run_id: str,
        request: CurriculumPipelineRequest,
        status: str,
        *,
        network: CurriculumKnowledgeNetwork | None = None,
        error: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO curriculum_runs(id, status, request_json, network_json, error, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    request_json=excluded.request_json,
                    network_json=COALESCE(excluded.network_json, curriculum_runs.network_json),
                    error=excluded.error,
                    updated_at=excluded.updated_at
                """,
                (
                    run_id,
                    status,
                    request.model_dump_json(),
                    network.model_dump_json() if network else None,
                    error,
                    utc_now().isoformat(),
                ),
            )

    def load_curriculum_network(self, run_id: str) -> CurriculumKnowledgeNetwork | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT network_json FROM curriculum_runs WHERE id = ?",
                (run_id,),
            ).fetchone()
        return CurriculumKnowledgeNetwork.model_validate_json(row[0]) if row and row[0] else None

    def record_curriculum_attempt(
        self,
        *,
        run_id: str,
        stage: str,
        unit_id: str,
        attempt_number: int,
        provider_name: str,
        candidate_id: str,
        payload: BaseModel,
        issues: list[ValidationIssue],
    ) -> None:
        validation_json = "[" + ",".join(item.model_dump_json() for item in issues) + "]"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO curriculum_attempts(
                    run_id, stage, unit_id, attempt_number, provider_name,
                    candidate_id, payload_json, validation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    stage,
                    unit_id,
                    attempt_number,
                    provider_name,
                    candidate_id,
                    payload.model_dump_json(),
                    validation_json,
                    utc_now().isoformat(),
                ),
            )

    def record_curriculum_review(
        self,
        *,
        run_id: str,
        stage: str,
        unit_id: str,
        attempt_number: int,
        report: SupervisionReport,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO curriculum_reviews(
                    run_id, stage, unit_id, attempt_number, report_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    stage,
                    unit_id,
                    attempt_number,
                    report.model_dump_json(),
                    utc_now().isoformat(),
                ),
            )

    def load_latest_curriculum_feedback(
        self,
        *,
        run_id: str,
        stage: str,
        unit_id: str,
    ) -> list[str]:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT report_json
                FROM curriculum_reviews
                WHERE run_id = ? AND stage = ? AND unit_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (run_id, stage, unit_id),
            ).fetchone()
        if not row:
            return []
        report = SupervisionReport.model_validate_json(row[0])
        if report.decision.value == "pass":
            return []
        return report.rerun_instructions or [issue.message for issue in report.issues]

    def record_curriculum_repairs(
        self,
        *,
        run_id: str,
        stage: str,
        unit_id: str,
        attempt_number: int,
        provider_name: str,
        repairs: list[dict],
    ) -> None:
        if not repairs:
            return
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO curriculum_repairs(
                    run_id, stage, unit_id, attempt_number, provider_name,
                    repairs_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    stage,
                    unit_id,
                    attempt_number,
                    provider_name,
                    json.dumps(repairs, ensure_ascii=False),
                    utc_now().isoformat(),
                ),
            )

    def save_curriculum_release(self, bundle: CurriculumReleaseBundle) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO curriculum_releases(release_id, version, bundle_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    bundle.manifest.release_id,
                    bundle.manifest.version,
                    bundle.model_dump_json(),
                    bundle.manifest.created_at.isoformat(),
                ),
            )

    def load_curriculum_release(self, version: str) -> CurriculumReleaseBundle | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT bundle_json FROM curriculum_releases WHERE version = ?",
                (version,),
            ).fetchone()
        return CurriculumReleaseBundle.model_validate_json(row[0]) if row else None

    def save_specialized_run(self, run: SpecializedProductionRun) -> None:
        run.updated_at = utc_now()
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO specialized_runs(id, status, payload_json, updated_at)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    status=excluded.status,
                    payload_json=excluded.payload_json,
                    updated_at=excluded.updated_at
                """,
                (run.id, run.status, run.model_dump_json(), run.updated_at.isoformat()),
            )

    def record_specialized_attempt(
        self,
        run_id: str,
        batch_id: str,
        attempt_number: int,
        artifact: SpecializedArtifact,
        issues: list[ValidationIssue],
    ) -> None:
        validation_json = "[" + ",".join(item.model_dump_json() for item in issues) + "]"
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO specialized_attempts(
                    run_id, batch_id, attempt_number, provider_name, candidate_id,
                    artifact_json, validation_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    batch_id,
                    attempt_number,
                    artifact.provider_name,
                    artifact.candidate_id,
                    artifact.model_dump_json(),
                    validation_json,
                    utc_now().isoformat(),
                ),
            )

    def record_specialized_review(
        self,
        run_id: str,
        batch_id: str,
        attempt_number: int,
        report: SupervisionReport,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO specialized_reviews(
                    run_id, batch_id, attempt_number, report_json, created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    run_id,
                    batch_id,
                    attempt_number,
                    report.model_dump_json(),
                    utc_now().isoformat(),
                ),
            )

    def save_specialized_release(self, bundle: SpecializedReleaseBundle) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO specialized_releases(release_id, version, bundle_json, created_at)
                VALUES (?, ?, ?, ?)
                """,
                (
                    bundle.manifest.release_id,
                    bundle.manifest.version,
                    bundle.model_dump_json(),
                    bundle.manifest.created_at.isoformat(),
                ),
            )

    def load_specialized_release(self, version: str) -> SpecializedReleaseBundle | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT bundle_json FROM specialized_releases WHERE version = ?",
                (version,),
            ).fetchone()
        return SpecializedReleaseBundle.model_validate_json(row[0]) if row else None
