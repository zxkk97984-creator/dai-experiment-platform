"""Add the immutable environment editor V2 control plane.

This migration is deliberately additive.  It keeps the old package catalog,
version/package links, image references, and build logs intact while creating
the draft/publication model used by the V2 editor.

Revision ID: 20260820_0001
Revises: 20260819_0003
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20260820_0001"
down_revision = "20260819_0003"
branch_labels = None
depends_on = None


_PEP503_SEPARATORS = re.compile(r"[-_.]+")


def _bigint_pk() -> sa.TypeEngine:
    """Use INTEGER on SQLite so test and disposable SQLite DBs autoincrement."""

    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def _json_value(value, default):
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        parsed = json.loads(value)
    except (TypeError, ValueError):
        return default
    return parsed


def _normalize_name(value: str) -> str:
    return _PEP503_SEPARATORS.sub("-", str(value).strip().lower())


def _canonical_json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _legacy_package_specs(bind, version_ids: set[int]) -> dict[int, list[dict]]:
    """Turn old catalog links into the V2 direct dependency shape.

    The old catalog has no system-package concept.  Its links therefore become
    exact Python direct dependencies.  A package name can occur more than once
    when it was sourced from different catalogs; V2 cannot represent that
    ambiguity, so the first display-order entry wins and the inferred result is
    marked in resolved_spec below.
    """

    if not version_ids:
        return {}

    metadata = sa.MetaData()
    pvp = sa.Table("profile_version_packages", metadata, autoload_with=bind)
    catalog = sa.Table("package_catalog", metadata, autoload_with=bind)
    rows = bind.execute(
        sa.select(
            pvp.c.environment_version_id,
            pvp.c.display_order,
            catalog.c.normalized_name,
            catalog.c.pip_name,
            catalog.c.locked_version,
            catalog.c.import_names,
            catalog.c.source_key,
        )
        .select_from(pvp.join(catalog, pvp.c.package_catalog_id == catalog.c.id))
        .where(pvp.c.environment_version_id.in_(version_ids))
        .order_by(pvp.c.environment_version_id, pvp.c.display_order, catalog.c.id)
    )

    specs: dict[int, list[dict]] = {version_id: [] for version_id in version_ids}
    seen: dict[int, set[str]] = {version_id: set() for version_id in version_ids}
    for row in rows:
        name = _normalize_name(row.pip_name or row.normalized_name)
        if not name or name in seen[row.environment_version_id]:
            continue
        seen[row.environment_version_id].add(name)
        import_names = _json_value(row.import_names, [])
        if not isinstance(import_names, list):
            import_names = []
        specs[row.environment_version_id].append(
            {
                "name": name,
                "version": str(row.locked_version) if row.locked_version is not None else None,
                "import_names": sorted({str(item) for item in import_names if str(item).strip()}),
            }
        )
    for values in specs.values():
        values.sort(key=lambda item: item["name"])
    return specs


def _legacy_resolved_spec(version_row, requested_packages: list[dict]) -> dict:
    """Create a truthful, explicitly inferred result for an old available image."""

    raw_resolved = _json_value(version_row.resolved_packages, {})
    if not isinstance(raw_resolved, dict):
        raw_resolved = {}

    normalized_resolved = {
        _normalize_name(name): str(value)
        for name, value in raw_resolved.items()
        if value is not None
    }
    direct_packages = []
    import_names = set()
    for requested in requested_packages:
        name = requested["name"]
        resolved_version = normalized_resolved.get(name, requested.get("version"))
        direct_packages.append(
            {
                "name": name,
                "requested_version": requested.get("version"),
                "resolved_version": resolved_version,
                "import_names": list(requested.get("import_names", [])),
                "hashes": [],
            }
        )
        import_names.update(requested.get("import_names", []))

    python_lock = [
        {"name": name, "version": version, "hashes": []}
        for name, version in sorted(normalized_resolved.items())
    ]
    lock_payload = {
        "python_lock": python_lock,
        "system_packages": [],
        "platform_python_packages": {},
    }
    lock_sha256 = hashlib.sha256(_canonical_json(lock_payload).encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "resolution_quality": "legacy_inferred",
        "direct_python_packages": direct_packages,
        "python_lock": python_lock,
        "system_packages": [],
        "import_names": sorted(import_names),
        "pip_check": {"ok": None, "message": "legacy result; not revalidated"},
        "base_image_ref": version_row.base_image_ref,
        "base_image_digest": None,
        "python_version": version_row.python_version or "3.12",
        "pip_version": None,
        "platform_python_packages": {},
        "platform_bundle_version": None,
        "pip_source_key": "legacy",
        "apt_snapshot_key": "legacy",
        "image_digest": version_row.image_digest,
        "image_size_bytes": None,
        "lock_sha256": lock_sha256,
        "warnings": [
            "This resolved specification was inferred from the legacy package catalog "
            "and existing build metadata; rebuild before relying on it as a lock file."
        ],
        "legacy_resolved_packages": raw_resolved,
    }


def _create_v2_tables() -> None:
    bigint_pk = _bigint_pk()

    op.create_table(
        "environment_drafts",
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("source_version_id", sa.BigInteger(), nullable=True),
        sa.Column("candidate_version_id", sa.BigInteger(), nullable=True),
        sa.Column("active_build_job_id", sa.BigInteger(), nullable=True),
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(length=16), nullable=False, server_default="editing"),
        sa.Column("python_version", sa.String(length=32), nullable=False, server_default="3.12"),
        sa.Column("minimum_memory_mb", sa.Integer(), nullable=False, server_default="256"),
        sa.Column(
            "requested_spec",
            sa.JSON(),
            nullable=False,
        ),
        sa.Column("created_by_id", sa.Integer(), nullable=True),
        sa.Column("updated_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["environment_profiles.id"],
            name="fk_env_drafts_profile", ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["source_version_id"], ["environment_versions.id"],
            name="fk_env_drafts_source_version",
        ),
        sa.ForeignKeyConstraint(
            ["candidate_version_id"], ["environment_versions.id"],
            name="fk_env_drafts_candidate_version",
        ),
        sa.ForeignKeyConstraint(
            ["active_build_job_id"], ["environment_build_jobs.id"],
            name="fk_env_drafts_active_build_job",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], name="fk_env_drafts_created_by"),
        sa.ForeignKeyConstraint(["updated_by_id"], ["users.id"], name="fk_env_drafts_updated_by"),
        sa.PrimaryKeyConstraint("profile_id", name="pk_environment_drafts"),
        sa.CheckConstraint(
            "state IN ('editing', 'building', 'ready', 'failed')",
            name="ck_env_drafts_state",
        ),
    )
    op.create_index(
        "ix_env_drafts_candidate_version_id",
        "environment_drafts",
        ["candidate_version_id"],
    )
    op.create_index(
        "ix_env_drafts_active_build_job_id",
        "environment_drafts",
        ["active_build_job_id"],
    )

    op.create_table(
        "environment_publications",
        sa.Column("id", bigint_pk, nullable=False),
        sa.Column("profile_id", sa.BigInteger(), nullable=False),
        sa.Column("version_id", sa.BigInteger(), nullable=False),
        sa.Column("previous_version_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=24), nullable=False),
        sa.Column("published_by_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(
            ["profile_id"], ["environment_profiles.id"],
            name="fk_env_publications_profile", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["version_id"], ["environment_versions.id"],
            name="fk_env_publications_version", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["previous_version_id"], ["environment_versions.id"],
            name="fk_env_publications_previous_version", ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["published_by_id"], ["users.id"], name="fk_env_publications_published_by"
        ),
        sa.PrimaryKeyConstraint("id", name="pk_environment_publications"),
        sa.CheckConstraint(
            "action IN ('publish', 'rollback', 'migration_baseline')",
            name="ck_env_publications_action",
        ),
    )
    op.create_index(
        "ix_env_publications_profile_created",
        "environment_publications",
        ["profile_id", "created_at"],
    )
    op.create_index(
        "ix_env_publications_version_id", "environment_publications", ["version_id"]
    )


def _backfill_data() -> None:
    bind = op.get_bind()
    metadata = sa.MetaData()
    profiles = sa.Table("environment_profiles", metadata, autoload_with=bind)
    versions = sa.Table("environment_versions", metadata, autoload_with=bind)
    jobs = sa.Table("environment_build_jobs", metadata, autoload_with=bind)
    drafts = sa.Table("environment_drafts", metadata, autoload_with=bind)
    publications = sa.Table("environment_publications", metadata, autoload_with=bind)

    version_rows = list(bind.execute(sa.select(versions).order_by(versions.c.id)))
    version_ids = {int(row.id) for row in version_rows}
    package_specs = _legacy_package_specs(bind, version_ids)

    for row in version_rows:
        requested = {
            "schema_version": 1,
            "python_packages": package_specs.get(int(row.id), []),
            "system_packages": [],
        }
        values = {
            "requested_spec": requested,
            "python_version": row.python_version or "3.12",
        }
        if row.status == "available" and row.image_digest:
            values["resolved_spec"] = _legacy_resolved_spec(row, requested["python_packages"])
            published_at = row.available_at or row.created_at or datetime.now(timezone.utc)
            values["first_published_at"] = published_at
            values["first_published_by_id"] = row.created_by_id
        bind.execute(versions.update().where(versions.c.id == row.id).values(**values))

    phase_by_status = {
        "queued": "queued",
        "building": "building",
        "succeeded": "done",
        "failed": "done",
        "timed_out": "done",
    }
    for row in bind.execute(sa.select(jobs.c.id, jobs.c.status)):
        bind.execute(
            jobs.update()
            .where(jobs.c.id == row.id)
            .values(phase=phase_by_status.get(row.status, "done"))
        )

    available_rows = list(
        bind.execute(
            sa.select(versions.c.id, versions.c.profile_id, versions.c.version_number)
            .where(versions.c.status == "available")
            .order_by(versions.c.profile_id, versions.c.version_number, versions.c.id)
        )
    )
    current_by_profile: dict[int, int] = {}
    for row in available_rows:
        current_by_profile[int(row.profile_id)] = int(row.id)
    for profile_id, version_id in current_by_profile.items():
        bind.execute(
            profiles.update()
            .where(profiles.c.id == profile_id)
            .values(current_version_id=version_id)
        )
        bind.execute(
            publications.insert().values(
                profile_id=profile_id,
                version_id=version_id,
                previous_version_id=None,
                action="migration_baseline",
                published_by_id=None,
            )
        )

    # Existing profiles did not have drafts.  Create an editable draft from
    # the chosen current version, while retaining the exact resolved package
    # versions so opening the editor does not silently upgrade a dependency.
    profile_rows = list(bind.execute(sa.select(profiles.c.id, profiles.c.current_version_id)))
    version_by_id = {int(row.id): row for row in version_rows}
    for profile in profile_rows:
        if profile.current_version_id is None:
            bind.execute(
                drafts.insert().values(
                    profile_id=profile.id,
                    source_version_id=None,
                    candidate_version_id=None,
                    active_build_job_id=None,
                    revision=1,
                    state="editing",
                    python_version="3.12",
                    minimum_memory_mb=256,
                    requested_spec={
                        "schema_version": 1,
                        "python_packages": [],
                        "system_packages": [],
                    },
                )
            )
            continue
        current = version_by_id[int(profile.current_version_id)]
        requested = {
            "schema_version": 1,
            "python_packages": package_specs.get(int(current.id), []),
            "system_packages": [],
        }
        bind.execute(
            drafts.insert().values(
                profile_id=profile.id,
                source_version_id=current.id,
                candidate_version_id=None,
                active_build_job_id=None,
                revision=1,
                state="editing",
                python_version=current.python_version or "3.12",
                minimum_memory_mb=current.minimum_memory_mb,
                requested_spec=requested,
            )
        )


def _add_v2_columns() -> None:
    op.add_column(
        "environment_profiles", sa.Column("current_version_id", sa.BigInteger(), nullable=True)
    )
    op.add_column("environment_versions", sa.Column("requested_spec", sa.JSON(), nullable=True))
    op.add_column("environment_versions", sa.Column("resolved_spec", sa.JSON(), nullable=True))
    op.add_column(
        "environment_versions",
        sa.Column("first_published_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "environment_versions", sa.Column("first_published_by_id", sa.Integer(), nullable=True)
    )
    op.add_column(
        "environment_build_jobs", sa.Column("phase", sa.String(length=32), nullable=True)
    )
    op.add_column("environment_build_jobs", sa.Column("error_detail", sa.JSON(), nullable=True))
    op.add_column("environment_build_jobs", sa.Column("result_summary", sa.JSON(), nullable=True))


def _make_non_null() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("environment_versions", recreate="always") as batch_op:
            batch_op.alter_column(
                "requested_spec", existing_type=sa.JSON(), existing_nullable=True, nullable=False
            )
            batch_op.alter_column(
                "python_version",
                existing_type=sa.String(length=32),
                existing_nullable=True,
                nullable=False,
            )
        with op.batch_alter_table("environment_build_jobs", recreate="always") as batch_op:
            batch_op.alter_column(
                "phase", existing_type=sa.String(length=32), existing_nullable=True, nullable=False
            )
        return

    # MySQL can alter these columns in place.  Avoid recreating tables that
    # are referenced by build jobs, package links, and the new publication
    # tables.
    op.alter_column(
        "environment_versions",
        "requested_spec",
        existing_type=sa.JSON(),
        existing_nullable=True,
        nullable=False,
    )
    op.alter_column(
        "environment_versions",
        "python_version",
        existing_type=sa.String(length=32),
        existing_nullable=True,
        nullable=False,
    )
    op.alter_column(
        "environment_build_jobs",
        "phase",
        existing_type=sa.String(length=32),
        existing_nullable=True,
        nullable=False,
    )


def _add_new_foreign_keys() -> None:
    # SQLite cannot ALTER TABLE ADD CONSTRAINT, so batch recreation is used for
    # both SQLite and MySQL.  The explicit names also remove SQLAlchemy's
    # relationship ambiguity around EnvironmentProfile.current_version_id.
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("environment_profiles", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                "fk_env_profiles_current_version",
                "environment_versions",
                ["current_version_id"],
                ["id"],
            )
        with op.batch_alter_table("environment_versions", recreate="always") as batch_op:
            batch_op.create_foreign_key(
                "fk_env_versions_first_published_by",
                "users",
                ["first_published_by_id"],
                ["id"],
            )
        return
    op.create_foreign_key(
        "fk_env_profiles_current_version",
        "environment_profiles",
        "environment_versions",
        ["current_version_id"],
        ["id"],
    )
    op.create_foreign_key(
        "fk_env_versions_first_published_by",
        "environment_versions",
        "users",
        ["first_published_by_id"],
        ["id"],
    )


def upgrade() -> None:
    _add_v2_columns()
    _create_v2_tables()
    _backfill_data()
    _make_non_null()
    _add_new_foreign_keys()


def _drop_foreign_keys() -> None:
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("environment_versions", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_env_versions_first_published_by", type_="foreignkey")
        with op.batch_alter_table("environment_profiles", recreate="always") as batch_op:
            batch_op.drop_constraint("fk_env_profiles_current_version", type_="foreignkey")
        return
    op.drop_constraint(
        "fk_env_versions_first_published_by", "environment_versions", type_="foreignkey"
    )
    op.drop_constraint(
        "fk_env_profiles_current_version", "environment_profiles", type_="foreignkey"
    )


def downgrade() -> None:
    # Drop the tables before their explicit indexes.  InnoDB may use the
    # version_id index as the supporting index for a foreign key, so dropping
    # that index first fails with MySQL error 1553.  DROP TABLE removes the
    # table-local indexes and constraints atomically on both supported dialects.
    op.drop_table("environment_publications")
    op.drop_table("environment_drafts")
    _drop_foreign_keys()
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("environment_build_jobs", recreate="always") as batch_op:
            batch_op.drop_column("result_summary")
            batch_op.drop_column("error_detail")
            batch_op.drop_column("phase")
        with op.batch_alter_table("environment_versions", recreate="always") as batch_op:
            batch_op.drop_column("first_published_by_id")
            batch_op.drop_column("first_published_at")
            batch_op.drop_column("resolved_spec")
            batch_op.drop_column("requested_spec")
        with op.batch_alter_table("environment_profiles", recreate="always") as batch_op:
            batch_op.drop_column("current_version_id")
        return
    op.drop_column("environment_build_jobs", "result_summary")
    op.drop_column("environment_build_jobs", "error_detail")
    op.drop_column("environment_build_jobs", "phase")
    op.drop_column("environment_versions", "first_published_by_id")
    op.drop_column("environment_versions", "first_published_at")
    op.drop_column("environment_versions", "resolved_spec")
    op.drop_column("environment_versions", "requested_spec")
    op.drop_column("environment_profiles", "current_version_id")
