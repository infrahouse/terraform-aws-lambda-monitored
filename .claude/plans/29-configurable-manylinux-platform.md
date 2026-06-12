# Task: Support `manylinux_2_28` wheels (issue #29)

Make this module install dependency wheels against **`manylinux_2_28`** (glibc 2.28)
so Lambdas can use packages that only publish `manylinux_2_28` wheels, e.g.
`pyarrow>=21` (the real consumer pin is `pyarrow>=23.0.1`, the CVE-2026-25087 fix).
Today `scripts/package.sh` hardcodes `manylinux2014_{arch}` (glibc 2.17), which makes
those packages uninstallable.

> Upstream issue: infrahouse/terraform-aws-lambda-monitored#29

## Root cause (for context)

`scripts/package.sh` installs wheels with:

```sh
PLATFORM="manylinux2014_x86_64"           # hardcoded from architecture only
pip install --only-binary=:all: --platform "${PLATFORM}" --python-version "${PY_VER}" ...
```

Because of `--only-binary=:all:`, pip can only pick a wheel matching that platform
tag. `pyarrow` ships `manylinux2014` wheels up to `20.0.0`; from `21.0.0` onward it
publishes **only** `manylinux_2_28`. So `pyarrow>=21` fails to resolve:

```
ERROR: Could not find a version that satisfies the requirement pyarrow>=23.0.1
       (from versions: ..., 20.0.0)
ERROR: No matching distribution found for pyarrow>=23.0.1
```

A `manylinux_2_28` wheel needs glibc ≥ 2.28 **at runtime**. Amazon Linux 2 (glibc
2.26) can't load it; only Amazon Linux 2023 (glibc 2.34) can — i.e. the python3.12+
Lambda runtimes.

## Design decision — AL2023-only, no new variable

**The module targets Amazon Linux 2023 Lambda runtimes only (python3.12 / 3.13).**
AL2-based runtimes (python ≤ 3.11) are dropped from the support matrix.

Rationale:

- `manylinux_2_28` is *not* an independent knob — it's a function of the runtime OS,
  which `python_version` (already a module input) fully determines. There's no
  configuration a consumer could supply that the runtime doesn't already dictate, so
  a `pip_platform` variable would only add a way to misconfigure (e.g. pairing
  `manylinux_2_28` with `python3.11` → builds fine, crashes at import).
- Amazon Linux 2 the OS is **EOL 2026-06-30**. AL2-based Lambda runtimes get
  backported patches into 2027 (python3.10 → Oct 2026, python3.11 → Jun 2027), but
  the consumer driving #29 is on python3.12+, and we don't want to carry a
  glibc-2.17 build path to serve runtimes that are already on their way out.

So: **no new variable.** `package.sh` installs against `manylinux_2_28_{arch}`
unconditionally. Under PEP 600 (perennial manylinux), a target supporting glibc 2.28
is also compatible with every lower tag (`manylinux2014` / `_2_17` and below), so
`pip` still resolves deps that only ship older `manylinux2014` wheels — mixed
dependency sets just work. A `python_version` validation rejects < 3.12 so misuse
fails fast at plan time with a clear message instead of a runtime glibc crash.

> **This is a breaking change.** Consumers on python ≤ 3.11 will get a plan-time
> validation error after upgrading. They must move to python3.12+ or pin the prior
> module release. → **major version bump.**

> Alternative considered (rejected): keep a version-gated branch
> (`manylinux2014` for ≤ 3.11, `manylinux_2_28` for ≥ 3.12) to preserve AL2 support
> until those runtimes deprecate in 2027. Cheap (one `if/else`) but keeps a
> glibc-2.17 code path and a 5-version support matrix alive for runtimes we've
> decided not to target. Revisit only if an AL2 consumer needs the new pyarrow,
> which is impossible anyway (glibc 2.26 can't load the 2_28 wheel).

---

## Phase 1 — Reproduce the bug with a failing integration test

Goal: a test that fails **with the exact pyarrow resolution error** on the current
(unfixed) code, using only existing module inputs.

> The test config does **not** change between red and green. The same fixture,
> `python_version="python3.12"`, and invocation go red here and green in Phase 3 —
> the only thing that flips is `package.sh`'s platform tag (Phase 2a). Don't toggle
> anything in the test to make it pass; if the test changes, it's no longer proving
> the production code path was fixed.

### 1a. New fixture — a dependency that only ships `manylinux_2_28`

`tests/fixtures/lambda_with_manylinux_2_28_deps/requirements.txt`
```text
pyarrow>=21.0.0
```

`tests/fixtures/lambda_with_manylinux_2_28_deps/main.py`
```python
"""Lambda fixture that imports pyarrow (manylinux_2_28-only wheels >= 21)."""

import json

import pyarrow


def lambda_handler(event, context):
    """Return the installed pyarrow version to prove the wheel loads at runtime."""
    return {
        "statusCode": 200,
        "body": json.dumps(
            {"success": True, "pyarrow_version": pyarrow.__version__}
        ),
    }
```

### 1b. New test class — `tests/test_module.py`

Hardcode `python3.12` + `x86_64` so this is a single deterministic case. Do **not**
consume the broad `python_version` / `architecture` parametrize fixtures here.

```python
class TestManylinux228:
    """Packages that only publish manylinux_2_28 wheels (issue #29)."""

    def test_manylinux_2_28_packaging(
        self,
        test_module_dir,
        fixtures_dir,
        lambda_client,
        keep_after,
        test_role_arn,
    ):
        function_name = "test-manylinux228-x8664-py312"
        lambda_source = fixtures_dir / "lambda_with_manylinux_2_28_deps"

        create_terraform_config(
            test_module_dir,
            lambda_source,
            function_name,
            "devnull@infrahouse.com",
            "~> 6.0",
            python_version="python3.12",
            architecture="x86_64",
            role_arn=test_role_arn,
        )

        with terraform_apply(
            str(test_module_dir),
            destroy_after=not keep_after,
            json_output=True,
        ) as tf_output:
            response = lambda_client.invoke(
                FunctionName=tf_output["lambda_function_name"]["value"],
                InvocationType="RequestResponse",
                Payload=json.dumps({}),
            )
            assert response["StatusCode"] == 200
            payload = json.loads(response["Payload"].read())
            assert payload["statusCode"] == 200, f"payload: {payload}"
            body = json.loads(payload["body"])
            assert body["success"] is True
            assert "pyarrow_version" in body
```

### 1c. New Makefile target (the repo groups tests per feature)

Add next to `test-deps`:

```makefile
.PHONY: test-manylinux
test-manylinux:  ## Run manylinux_2_28 wheel packaging tests (issue #29)
	$(call run_pytest,TestManylinux228,tests/test_module.py)
```

### 1d. Run it and confirm it FAILS

```bash
make test-manylinux KEEP_AFTER=1
```

Requires AWS credentials for the tester role (`TEST_ROLE`,
`arn:aws:iam::303467602807:role/lambda-monitored-tester`, region `us-west-2`).

**Expected (red):** `terraform apply` fails inside the `null_resource.lambda_package`
local-exec with `No matching distribution found for pyarrow>=21.0.0` — the same error
as the downstream CD failure.

---

## Phase 2 — Implement the fix

### 2a. `scripts/package.sh` — install against `manylinux_2_28`

Replace the arch→`PLATFORM` mapping (currently lines ~78–90, the `case "${ARCH}"`
block that produces `manylinux2014_{arch}`) with `manylinux_2_28_{arch}`:

```sh
# Install against manylinux_2_28 (glibc 2.28). This is the Amazon Linux 2023
# floor, which all supported Lambda Python runtimes (python3.12+) run on.
# Under PEP 600, pip also accepts every older tag (manylinux2014 and below) for
# deps that don't ship a 2_28 wheel.
case "${ARCH}" in
    aarch64)
        PLATFORM="manylinux_2_28_aarch64"
        ;;
    x86_64)
        PLATFORM="manylinux_2_28_x86_64"
        ;;
    *)
        echo "Error: Could not map architecture to manylinux platform: ${ARCH}" >&2
        exit 1
        ;;
esac
```

No other change to `package.sh`: the existing `--platform "${PLATFORM}"` install line
picks it up, and `PY_VER` is unchanged.

> No `lambda_code.tf` change is needed. `package_hash` already includes
> `var.python_version` and `local.module_version`; the module-version bump that ships
> this fix forces a repackage for existing consumers, so the new platform takes
> effect on upgrade.

### 2b. `variables.tf` — restrict `python_version` to AL2023 runtimes

Tighten the existing validation (currently allows `3.(9|10|11|12|13)`):

```hcl
variable "python_version" {
  description = <<-EOT
    Python runtime version. Must be an Amazon Linux 2023 runtime (python3.12 or
    python3.13) — this module installs manylinux_2_28 wheels (glibc 2.28), which
    only AL2023 runtimes can load. See
    https://docs.aws.amazon.com/lambda/latest/dg/lambda-runtimes.html
  EOT
  type        = string
  default     = "python3.12"

  validation {
    condition     = can(regex("^python3\\.(12|13)$", var.python_version))
    error_message = "Python version must be python3.12 or python3.13 (Amazon Linux 2023 runtimes). Earlier runtimes (Amazon Linux 2) cannot load manylinux_2_28 wheels."
  }
}
```

---

## Phase 3 — Make the test green + adjust the support matrix

### 3a. Drop python ≤ 3.11 from test parametrization

In `tests/conftest.py` (the `python_version` fixture, currently line ~321):

```python
params=["python3.12", "python3.13"],   # was ["python3.11", "python3.12", "python3.13"]
```

This makes `test-simple`, `test-deps`, etc. exercise only the supported runtimes.

### 3b. Re-run the new test — confirm GREEN

```bash
make test-manylinux KEEP_AFTER=1
```

Expected: apply succeeds, Lambda invokes, returns `pyarrow_version`.

### 3c. Regression guard

Run the existing dependency suite (now python3.12/3.13 only) and confirm it still
passes — proves the `manylinux_2_28` floor doesn't break deps that previously
resolved against `manylinux2014`:

```bash
make test-deps KEEP_AFTER=1
```

---

## Phase 4 — Commit & PR

- Branch from `main` (e.g. `feat/manylinux-2-28`).
- **Conventional commits** (per CONTRIBUTING.md / `cliff.toml`). Because dropping
  python ≤ 3.11 is breaking, use a `!` / `BREAKING CHANGE:` footer so git-cliff cuts a
  **major** release. Suggested split:
  - `test: reproduce manylinux_2_28-only wheel packaging failure (#29)`
  - `feat!: install manylinux_2_28 wheels; require AL2023 runtime (python3.12+) (#29)`
    with a `BREAKING CHANGE:` footer explaining python ≤ 3.11 is no longer supported.
- **Do not hand-edit `CHANGELOG.md`** — git-cliff owns it and regenerates it from
  commit messages. Put the release-notes content in the commit body instead.
- Run `terraform fmt -recursive` and `make lint` before pushing; the pre-commit hook
  regenerates the terraform-docs README block (python_version description/default).
- Open the PR: reference #29, state the breaking AL2023-only requirement and the new
  `test-manylinux` target. Ensure CI passes.

## Acceptance criteria

- [ ] `make test-manylinux KEEP_AFTER=1` fails on current code with the
      `No matching distribution found for pyarrow` error (Phase 1).
- [ ] After the fix, the same test passes (apply + invoke + `pyarrow_version`).
- [ ] `package.sh` installs against `manylinux_2_28_{arch}`; no new variable added.
- [ ] `python_version` validation rejects python ≤ 3.11 with a clear message.
- [ ] Test parametrization covers only python3.12 / 3.13; `make test-deps` passes.
- [ ] README/terraform-docs regenerated (python_version description + matrix docs).
- [ ] PR references #29; conventional commits with `BREAKING CHANGE:`; major bump.

## Downstream follow-up (not part of this PR)

`aws-control-root` `modules/aws-cost-report/terraform/main.tf` bumps the
module to the new **major** release and sets `python_version = "python3.12"` (or
`python3.13`). No `pip_platform` to set — the manylinux_2_28 floor is built in, and
the 3.12+ runtime is what loads the `manylinux_2_28` wheel (pyarrow 23.0.1, the
CVE-2026-25087 fix) at runtime.
