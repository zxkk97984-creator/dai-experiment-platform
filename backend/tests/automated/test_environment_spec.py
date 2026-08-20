import pytest

from app.config import Settings
from app.schemas.environments import RequestedEnvironmentSpec
from app.services.environment_spec import (
    DEFAULT_MEMORY_MB,
    DEFAULT_PYTHON_VERSION,
    canonical_requested_spec,
    normalize_requested_spec,
    requested_spec_sha256,
    validate_python_version,
)


def test_normalize_requested_spec_is_canonical_and_applies_defaults():
    spec = normalize_requested_spec(
        {
            "schema_version": 1,
            "python_packages": [
                {"name": "scikit_learn", "version": None, "import_names": ["sklearn.metrics", "sklearn"]},
                {"name": "NumPy", "version": "2.1.3", "import_names": []},
            ],
            "system_packages": [
                {"name": "ffmpeg", "version": None},
                {"name": "libx264+dev", "version": "1:164.3095-1"},
            ],
        }
    )

    assert spec == {
        "schema_version": 1,
        "python_packages": [
            {"name": "numpy", "version": "2.1.3", "import_names": []},
            {"name": "scikit-learn", "version": None, "import_names": ["sklearn"]},
        ],
        "system_packages": [
            {"name": "ffmpeg", "version": None},
            {"name": "libx264+dev", "version": "1:164.3095-1"},
        ],
    }


def test_requested_spec_hash_is_stable_across_input_order():
    left = {
        "schema_version": 1,
        "python_packages": [{"name": "pandas", "version": None, "import_names": []}],
        "system_packages": [],
    }
    right = {
        "system_packages": [],
        "python_packages": [{"import_names": [], "version": None, "name": "PANDAS"}],
        "schema_version": 1,
    }

    assert canonical_requested_spec(left) == canonical_requested_spec(right)
    assert requested_spec_sha256(left) == requested_spec_sha256(right)


def test_python_version_allowlist_and_exact_versions():
    assert validate_python_version("3.10") == "3.10"
    assert validate_python_version("3.12") == "3.12"
    assert DEFAULT_PYTHON_VERSION == "3.12"
    assert DEFAULT_MEMORY_MB == 256

    with pytest.raises(ValueError, match="Python 版本不受支持"):
        validate_python_version("3.13")

    with pytest.raises(ValueError, match="Python 版本不受支持"):
        validate_python_version("3.12.1")


@pytest.mark.parametrize(
    "bad_spec",
    [
        {"schema_version": 1, "python_packages": [{"name": "numpy==2.0", "version": None}], "system_packages": []},
        {"schema_version": 1, "python_packages": [{"name": "https://evil.example/pkg", "version": None}], "system_packages": []},
        {"schema_version": 1, "python_packages": [{"name": "numpy", "version": ">=2.0"}], "system_packages": []},
        {"schema_version": 1, "python_packages": [{"name": "numpy", "version": "2.*"}], "system_packages": []},
        {"schema_version": 1, "python_packages": [{"name": "numpy", "version": None, "import_names": ["os;rm"]}], "system_packages": []},
        {"schema_version": 1, "python_packages": [], "system_packages": [{"name": "apt-get --yes", "version": None}]},
        {"schema_version": 1, "python_packages": [], "system_packages": [{"name": "ffmpeg:amd64", "version": None}]},
        {"schema_version": 1, "python_packages": [], "system_packages": [{"name": "ffmpeg", "version": "1.0 && id"}]},
    ],
)
def test_requested_spec_rejects_injection_and_non_exact_versions(bad_spec):
    with pytest.raises(ValueError):
        normalize_requested_spec(bad_spec)


def test_requested_spec_rejects_duplicate_packages_after_normalization():
    with pytest.raises(ValueError, match="Python 包不能重复"):
        normalize_requested_spec(
            {
                "schema_version": 1,
                "python_packages": [
                    {"name": "scikit-learn", "version": None},
                    {"name": "scikit_learn", "version": "1.6.0"},
                ],
                "system_packages": [],
            }
        )

    with pytest.raises(ValueError, match="系统包不能重复"):
        normalize_requested_spec(
            {
                "schema_version": 1,
                "python_packages": [],
                "system_packages": [
                    {"name": "ffmpeg", "version": None},
                    {"name": "ffmpeg", "version": None},
                ],
            }
        )


def test_requested_spec_enforces_direct_dependency_limits():
    with pytest.raises(ValueError, match="Python 直接依赖最多 100 个"):
        normalize_requested_spec(
            {
                "schema_version": 1,
                "python_packages": [{"name": f"pkg{i}", "version": None} for i in range(101)],
                "system_packages": [],
            }
        )

    with pytest.raises(ValueError, match="系统直接依赖最多 50 个"):
        normalize_requested_spec(
            {
                "schema_version": 1,
                "python_packages": [],
                "system_packages": [{"name": f"pkg{i}", "version": None} for i in range(51)],
            }
        )


def test_requested_spec_requires_known_schema_and_shape():
    with pytest.raises(ValueError, match="schema_version"):
        normalize_requested_spec({"schema_version": 2, "python_packages": [], "system_packages": []})

    with pytest.raises(ValueError, match="未知字段"):
        normalize_requested_spec(
            {
                "schema_version": 1,
                "python_packages": [],
                "system_packages": [],
                "shell": "rm -rf /",
            }
        )


def test_v2_settings_have_safe_editor_defaults():
    settings = Settings(_env_file=None)

    assert settings.environment_editor_v2_enabled is False
    assert set(settings.env_python_base_images) == {"3.10", "3.11", "3.12"}
    assert settings.env_platform_python_packages["ipykernel"] == "6.29.5"
    assert settings.env_platform_python_packages["pytest"] == "8.3.4"
    assert settings.env_build_network_mode == "default"
    assert settings.env_build_max_image_bytes == 20 * 1024 * 1024 * 1024


def test_requested_environment_schema_uses_the_domain_normalizer():
    spec = RequestedEnvironmentSpec(
        python_packages=[{"name": "NumPy", "version": None}],
        system_packages=[{"name": "ffmpeg", "version": None}],
    )

    assert spec.schema_version == 1
    assert spec.python_packages[0].name == "numpy"
    assert spec.system_packages[0].name == "ffmpeg"


def test_v2_production_requires_digest_for_every_python_base_image():
    with pytest.raises(ValueError, match="ENV_PYTHON_BASE_IMAGES"):
        Settings(
            _env_file=None,
            environment="production",
            secret_key="a-very-secure-key-32chars!",
            database_url="mysql+pymysql://safe:pass@localhost/db",
            cors_origins="https://myapp.example.com",
            environment_editor_v2_enabled=True,
            env_base_image="python:3.12-slim@sha256:" + "0" * 64,
            env_python_base_images={
                "3.10": "python:3.10-slim-bookworm",
                "3.11": "python:3.11-slim-bookworm@sha256:" + "1" * 64,
                "3.12": "python:3.12-slim-bookworm@sha256:" + "2" * 64,
            },
        )
