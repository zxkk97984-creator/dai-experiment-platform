# Kernel Environment Runner Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ensure every available teacher-selected environment builds a usable Kernel image and that preview execution invokes the runner path embedded in that image.

**Architecture:** Environment versions remain immutable and are selected by `environment_version_id`; runtime resolves the version to an image digest. The builder embeds one trusted runner at `/opt/dai/kernel_runner.py`, while the KernelManager uses that path and retains a legacy fallback for the existing `dai-kernel-python:latest` image. Empty or missing runner source must fail the build before publishing an environment version.

**Tech Stack:** FastAPI/Python, Docker, SQLAlchemy, Redis, pytest.

---

### Task 1: Add regression coverage for runner source and runtime path

**Files:**
- Modify: `backend/tests/automated/test_environment_builder.py`
- Modify: `backend/tests/automated/test_kernel_runner.py`

- [x] **Step 1: Add a test that the canonical build spec loads the repository runner source.**

  Assert that `spec.kernel_runner_source` is non-empty and contains `BlockingKernelClient` when built from the repository path.

- [x] **Step 2: Add a test that KernelManager selects the environment runner path.**

  Assert that the generated `docker exec` argv contains `/opt/dai/kernel_runner.py` for an environment-backed session.

- [x] **Step 3: Run the two focused tests and confirm the current implementation exposes the regression.**

  Run from the repository root:

  ```cmd
  backend\.venv\Scripts\python.exe -m pytest backend/tests/automated/test_environment_builder.py backend/tests/automated/test_kernel_runner.py -q
  ```

### Task 2: Fix source loading and image validation

**Files:**
- Modify: `backend/app/services/environment_builder.py`

- [x] **Step 1: Correct the repository path calculation.**

  Change `_KERNEL_RUNNER_PATH` from `parents[1] / "docker" / "kernel" / "kernel_runner.py"` to `parents[2] / "docker" / "kernel" / "kernel_runner.py"`, because `environment_builder.py` is under `backend/app/services`.

- [x] **Step 2: Stop silently producing an empty runner.**

  Make `_load_kernel_runner()` raise `RuntimeError` when the source is missing or empty, and make `execute_build()` reject an empty `runner_text` before writing the temporary Docker build context. This prevents a broken image from being published as `available`.

- [x] **Step 3: Render environment images with the canonical runner path.**

  Keep the generated Dockerfile copy target as `/opt/dai/kernel_runner.py` and add a non-empty file check to the offline smoke validation.

### Task 3: Fix runtime execution path with legacy compatibility

**Files:**
- Modify: `backend/app/services/kernel_manager.py`
- Modify: `backend/tests/automated/test_kernel_runner.py`

- [x] **Step 1: Define `/opt/dai/kernel_runner.py` as the canonical path and `/.dai/kernel_runner.py` as the legacy path.**

- [x] **Step 2: Resolve the runner path once per environment session by validating the non-empty file inside the container.**

  Prefer `/opt/dai/kernel_runner.py`; fall back to `/.dai/kernel_runner.py` for old unbound `dai-kernel-python:latest` sessions; raise a clear runtime error if neither exists.

- [x] **Step 3: Keep student code only in stdin JSON and never in Docker argv.**

### Task 4: Verify rebuild and environment switching

**Files:**
- No source files beyond Tasks 2–3.

- [x] **Step 1: Run focused and related backend tests. The full automated suite was attempted but exceeded the 304-second command limit without producing a failure summary.**

- [x] **Step 2: Built fixed v2 images for the three existing profiles and verified a 2046-byte runner in each.**

- [x] **Step 3: Recreated the current preview session and executed the NumPy cell through `/opt/dai/kernel_runner.py`.**

- [x] **Step 4: Verified Python Basic, Data Analysis, and PyTorch CPU sessions use distinct v2 image digests and corresponding imports execute.**

- [x] **Step 5: All three v2 environment builds and image smoke checks succeeded.**
