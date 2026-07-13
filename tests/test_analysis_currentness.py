"""Fail-closed currentness contract for the bounded KPZ analysis pipeline.

These tests intentionally exercise provenance and cache resolution rather than
the scientific estimators.  Managed hierarchical raw runs are simulation
artifacts, not an analysis input layout: they must first be reduced to declared
``pct_NN/L_LLLL.npz`` traces.  Historical flat joblibs remain available only
through an explicit, non-ambiguous compatibility layout.
"""

from __future__ import annotations

import hashlib
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

import joblib
import numpy as np
import pytest

import tetris_ballistic.kpz_analysis as kpz_analysis
from tetris_ballistic.analysis_artifacts import (
    INPUT_SET_PROFILE,
    AnalysisArtifactValidationError,
    analysis_artifact_paths,
    build_analysis_identity,
    build_identity,
    canonical_json_bytes,
    write_json_artifact,
)
from tetris_ballistic.kpz_analysis import load_ensemble, resolve_ensemble_input
from tetris_ballistic.scripts import run_kpz_analysis as runner
from tetris_ballistic.scripts.invert_exp14_height import (
    grid_height_for_L,
    invert_cell,
)


def _write_reduced_cell(
    root: Path,
    *,
    pct: int = 50,
    width: int = 20,
    marker: float = 11.0,
    index_dtype=np.int64,
) -> Path:
    path = root / f"pct_{pct:02d}" / f"L_{width:04d}.npz"
    path.parent.mkdir(parents=True, exist_ok=True)
    steps = 32
    seeds = np.asarray([0, 10], dtype=index_dtype)
    hbar = np.tile(np.linspace(1.0, 100.0, steps, dtype=np.float32), (2, 1))
    width_trace = np.full(hbar.shape, marker, dtype=np.float32)
    np.savez_compressed(
        path,
        seeds=seeds,
        final_steps=np.full(seeds.shape, steps, dtype=index_dtype),
        W=width_trace,
        hbar=hbar,
        pct=np.int32(pct),
        L=np.int32(width),
        hbar_max=np.float32(hbar.mean(axis=0)[-1]),
        saturated=np.bool_(hbar.mean(axis=0)[-1] >= width**1.5),
    )
    return path


def _write_legacy_flat_cell(
    root: Path,
    *,
    pct: int = 50,
    width: int = 20,
    seed: int = 0,
    marker: float = 22.0,
) -> Path:
    path = root / (
        f"config_piece_19_combined_percentage_{pct:02d}_"
        f"w={width}_seed={seed}.joblib"
    )
    trace = np.full(32, marker, dtype=np.float64)
    config = {f"Piece-{piece}": [0, 0] for piece in range(20)}
    config["Piece-19"] = [pct, 100 - pct]
    config.update({"height": 200, "seed": seed, "steps": trace.size, "width": width})
    joblib.dump(
        SimpleNamespace(
            FinalSteps=trace.size,
            Fluctuation=trace,
            AvergeHeight=np.linspace(1.0, 100.0, trace.size),
            config_data=config,
            seed=seed,
            width=width,
        ),
        path,
    )
    return path


def _base_identity(
    *,
    percentage: int = 50,
    width: int = 20,
    input_sha256: str = "1" * 64,
    n_boot: int = 200,
    n_eval: int = 3,
    software_sha256: str = "2" * 64,
    root_seed: int = 42,
    min_seeds: int = 2,
    percentage_convention: str = "sticky-fraction",
) -> dict[str, object]:
    content = build_identity(
        INPUT_SET_PROFILE,
        {
            "files": [
                {
                    "path": f"pct_{percentage:02d}/L_{width:04d}.npz",
                    "sha256": input_sha256,
                    "size_bytes": 1234,
                }
            ]
        },
    )
    inputs = build_identity(
        runner.CELL_INPUT_PROFILE,
        {
            "content": content,
            "layout": "reduced",
            "seed_inventory": [0, 10],
        },
    )
    software = build_identity(
        "test-software-sha256-v1",
        {"source_sha256": software_sha256},
    )
    return build_analysis_identity(
        artifact_kind="kpz-cell-v1",
        context={
            "L": width,
            "input_layout": "reduced",
            "percentage": percentage,
            "percentage_convention": percentage_convention,
            "model_profile": "piece-19-one-cell-v1",
        },
        inputs=inputs,
        rng={
            "algorithm": "numpy.random.PCG64",
            "derivation": "direct-per-estimator-v1",
            "root_seed": root_seed,
        },
        settings={
            "min_seeds": min_seeds,
            "n_boot": n_boot,
            "n_eval": n_eval,
            "sampling_policy": dict(runner.SAMPLING_POLICY),
        },
        software=software,
    )


def _test_software_identity(source_sha256: str = "2" * 64) -> dict[str, object]:
    return build_identity(
        "test-software-sha256-v1",
        {"source_sha256": source_sha256},
    )


def _production_identity(
    trace_root: Path,
    *,
    percentage: int = 50,
    width: int = 20,
    n_boot: int = 200,
    n_eval: int = 3,
    root_seed: int = 42,
    software_sha256: str = "2" * 64,
    min_seeds: int = 2,
    percentage_convention: str = "sticky-fraction",
) -> dict[str, object]:
    return runner._cell_identity(
        str(trace_root),
        percentage,
        width,
        input_layout="reduced",
        n_boot=n_boot,
        n_eval=n_eval,
        rng_seed=root_seed,
        min_seeds=min_seeds,
        percentage_convention=percentage_convention,
        software=_test_software_identity(software_sha256),
    )


def _cached_cell(*, percentage: int = 50, width: int = 20) -> dict[str, object]:
    return {
        "L": width,
        "analysis_point_count": 32,
        "beta_err_for_extrap": 0.01,
        "beta_for_extrap": 0.33,
        "eval_log_t": [1.0, 2.0, 3.0],
        "growth_window_beta": 0.33,
        "growth_window_ci": [0.32, 0.34],
        "hbar_max": 100.0,
        "meakin_window1": {"se": 0.01, "slope": 0.32},
        "meakin_window2": {"se": 0.01, "slope": 0.34},
        "min_trace_len": 32,
        "model_profile": "piece-19-one-cell-v1",
        "n_seeds": 2,
        "percentage": percentage,
        "percentage_convention": "sticky-fraction",
        "plateau_detected": False,
        "plateau_mask": [False, False, False],
        "sampling_policy": dict(runner.SAMPLING_POLICY),
        "saturated": 100.0 >= width**1.5,
        "slope_hi": [0.34, 0.35, 0.36],
        "slope_lo": [0.30, 0.31, 0.32],
        "slope_med": [0.32, 0.33, 0.34],
    }


def _load_cached_cell(path: Path, expected_identity: dict[str, object]):
    loader = getattr(runner, "_load_cached_cell", None)
    assert callable(loader), "run_kpz_analysis must provide strict _load_cached_cell"
    return loader(str(path), expected_identity)


def _assert_cache_rejected(path: Path, expected_identity: dict[str, object]) -> None:
    try:
        observed = _load_cached_cell(path, expected_identity)
    except (AnalysisArtifactValidationError, ValueError):
        return
    assert observed is None, "stale or corrupt cache payload was reused"


def _write_cached_cell(
    path: Path,
    identity: dict[str, object],
    cell: dict[str, object] | None = None,
) -> None:
    context = identity["record"]["context"]
    write_json_artifact(
        path,
        (
            _cached_cell(
                percentage=context["percentage"],
                width=context["L"],
            )
            if cell is None
            else cell
        ),
        identity,
    )


def _replace_managed_payload(path: Path, payload: bytes) -> None:
    """Tamper payload and checksum together so validation reaches JSON decode."""

    path.write_bytes(payload)
    manifest_path = analysis_artifact_paths(path).manifest
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifact"]["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest["artifact"]["size_bytes"] = len(payload)
    manifest_path.write_bytes(canonical_json_bytes(manifest) + b"\n")


def test_default_layout_is_reduced_and_never_falls_back_to_legacy(tmp_path: Path) -> None:
    _write_legacy_flat_cell(tmp_path)

    with pytest.raises(ValueError, match="reduced"):
        load_ensemble(str(tmp_path), 50, 20)

    legacy_W, _ = load_ensemble(
        str(tmp_path),
        50,
        20,
        input_layout="legacy-flat",
        percentage_convention="nonsticky-fraction",
    )
    assert legacy_W[0][0] == pytest.approx(22.0)


def test_reduced_and_legacy_flat_layouts_never_shadow_each_other(tmp_path: Path) -> None:
    _write_reduced_cell(tmp_path, marker=11.0)
    _write_legacy_flat_cell(tmp_path, marker=22.0)

    reduced_W, _ = load_ensemble(
        str(tmp_path), 50, 20, input_layout="reduced"
    )
    legacy_W, _ = load_ensemble(
        str(tmp_path),
        50,
        20,
        input_layout="legacy-flat",
        percentage_convention="nonsticky-fraction",
    )

    assert reduced_W[0][0] == pytest.approx(11.0)
    assert legacy_W[0][0] == pytest.approx(22.0)


def test_each_explicit_layout_refuses_the_other_layout(tmp_path: Path) -> None:
    legacy_only = tmp_path / "legacy"
    legacy_only.mkdir()
    _write_legacy_flat_cell(legacy_only)
    with pytest.raises(ValueError, match="reduced"):
        load_ensemble(
            str(legacy_only), 50, 20, input_layout="reduced"
        )

    reduced_only = tmp_path / "reduced"
    reduced_only.mkdir()
    _write_reduced_cell(reduced_only)
    with pytest.raises(ValueError, match="legacy-flat|legacy flat"):
        load_ensemble(
            str(reduced_only), 50, 20, input_layout="legacy-flat"
        )


def test_reduced_layout_rejects_embedded_cell_identity_mismatch(tmp_path: Path) -> None:
    path = _write_reduced_cell(tmp_path, pct=99, width=999)
    requested = tmp_path / "pct_50" / "L_0020.npz"
    requested.parent.mkdir(parents=True)
    path.replace(requested)

    with pytest.raises(ValueError, match="identity|pct|width|L"):
        load_ensemble(str(tmp_path), 50, 20, input_layout="reduced")


def test_reduced_layout_rejects_arbitrary_trace_truncation(tmp_path: Path) -> None:
    path = _write_reduced_cell(tmp_path)
    with np.load(path, allow_pickle=False) as trace:
        data = {name: trace[name] for name in trace.files}
    data["W"] = data["W"][:, :10]
    data["hbar"] = data["hbar"][:, :10]
    data["hbar_max"] = np.float32(data["hbar"].mean(axis=0)[-1])
    data["saturated"] = np.bool_(data["hbar_max"] >= 20**1.5)
    np.savez_compressed(path, **data)

    with pytest.raises(ValueError, match=r"min\(final_steps\)|length"):
        load_ensemble(str(tmp_path), 50, 20, input_layout="reduced")


def test_reduced_layout_accepts_canonical_int32_index_arrays(tmp_path: Path) -> None:
    _write_reduced_cell(tmp_path, index_dtype=np.int32)

    selected = resolve_ensemble_input(
        str(tmp_path), 50, 20, input_layout="reduced"
    )
    W_list, hbar_list = load_ensemble(
        str(tmp_path), 50, 20, input_layout="reduced", resolved_input=selected
    )

    assert selected.seeds == (0, 10)
    assert len(W_list) == len(hbar_list) == 2


def test_reduced_validation_uses_bounded_one_dimensional_chunks(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _write_reduced_cell(tmp_path)
    original_diff = np.diff
    observed_shapes = []

    def bounded_diff(values, *args, **kwargs):
        observed_shapes.append(values.shape)
        return original_diff(values, *args, **kwargs)

    monkeypatch.setattr(kpz_analysis, "_REDUCED_VALIDATION_CHUNK_POINTS", 5)
    monkeypatch.setattr(kpz_analysis.np, "diff", bounded_diff)

    load_ensemble(str(tmp_path), 50, 20, input_layout="reduced")

    assert observed_shapes
    assert all(len(shape) == 1 and shape[0] <= 5 for shape in observed_shapes)


def test_reduced_layout_rejects_decreasing_mean_height(tmp_path: Path) -> None:
    path = _write_reduced_cell(tmp_path)
    with np.load(path, allow_pickle=False) as trace:
        data = {name: trace[name] for name in trace.files}
    data["hbar"][0, 10] = data["hbar"][0, 9] - np.float32(1.0)
    data["hbar_max"] = np.float32(data["hbar"].mean(axis=0)[-1])
    np.savez_compressed(path, **data)

    with pytest.raises(ValueError, match="nondecreasing"):
        load_ensemble(str(tmp_path), 50, 20, input_layout="reduced")


def test_official_exp14_height_migration_emits_a_loadable_schema(tmp_path: Path) -> None:
    path = _write_reduced_cell(tmp_path)
    with np.load(path, allow_pickle=False) as trace:
        data = {name: trace[name] for name in trace.files}
    height_grid = grid_height_for_L(20)
    data["hbar"] = (height_grid - data["hbar"]).astype(np.float32)
    data["hbar_max"] = np.float32(data["hbar"].mean(axis=0)[-1])
    data["saturated"] = np.bool_(data["hbar_max"] >= 20**1.5)
    np.savez_compressed(path, **data)

    assert invert_cell(str(path), dry_run=False).startswith("inverted")
    W_list, hbar_list = load_ensemble(
        str(tmp_path), 50, 20, input_layout="reduced"
    )

    with np.load(path, allow_pickle=False) as migrated:
        assert set(migrated.files) == {
            "L",
            "W",
            "final_steps",
            "hbar",
            "hbar_max",
            "height_grid",
            "pct",
            "saturated",
            "seeds",
        }
        assert int(migrated["height_grid"]) == height_grid
    assert len(W_list) == len(hbar_list) == 2
    assert all(np.all(np.diff(trace) >= 0) for trace in hbar_list)


def test_legacy_layout_rejects_decreasing_mean_height(tmp_path: Path) -> None:
    path = _write_legacy_flat_cell(tmp_path)
    simulation = joblib.load(path)
    simulation.AvergeHeight[10] = simulation.AvergeHeight[9] - 1.0
    joblib.dump(simulation, path)

    with pytest.raises(ValueError, match="nondecreasing"):
        load_ensemble(
            str(tmp_path),
            50,
            20,
            input_layout="legacy-flat",
            percentage_convention="nonsticky-fraction",
        )


def test_legacy_layout_rejects_complex_observables(tmp_path: Path) -> None:
    path = _write_legacy_flat_cell(tmp_path)
    simulation = joblib.load(path)
    simulation.Fluctuation = simulation.Fluctuation.astype(complex) + 1j
    joblib.dump(simulation, path)

    with pytest.raises(ValueError, match="observables are invalid"):
        load_ensemble(
            str(tmp_path),
            50,
            20,
            input_layout="legacy-flat",
            percentage_convention="nonsticky-fraction",
        )


def test_legacy_layout_rejects_renamed_embedded_identity(tmp_path: Path) -> None:
    path = _write_legacy_flat_cell(tmp_path, pct=50, width=20, seed=7)
    simulation = joblib.load(path)
    simulation.width = 999
    simulation.seed = 999
    joblib.dump(simulation, path)

    with pytest.raises(ValueError, match="embedded width|embedded seed|identity"):
        load_ensemble(
            str(tmp_path),
            50,
            20,
            input_layout="legacy-flat",
            percentage_convention="nonsticky-fraction",
        )


def test_legacy_resolved_input_cannot_be_reused_for_another_cell(tmp_path: Path) -> None:
    _write_legacy_flat_cell(tmp_path, pct=90, width=30)
    selected = resolve_ensemble_input(
        str(tmp_path), 90, 30, input_layout="legacy-flat"
    )

    with pytest.raises(ValueError, match="identity|percentage|width|cell|request"):
        load_ensemble(
            str(tmp_path),
            50,
            20,
            input_layout="legacy-flat",
            resolved_input=selected,
        )


def test_hierarchical_managed_raw_requires_reduction_and_never_false_succeeds(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    input_root = tmp_path / "managed-results"
    raw_cell = input_root / "pct_50" / "L_0020" / "seed_000.joblib"
    raw_cell.parent.mkdir(parents=True)
    raw_cell.write_bytes(b"hierarchical-managed-placeholder")
    output_root = tmp_path / "analysis"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_kpz_analysis",
            "--trace-root",
            str(input_root),
            "--out-dir",
            str(output_root),
            "--input-layout",
            "reduced",
            "--percentage-convention",
            "sticky-fraction",
            "--model-profile",
            "piece-19-one-cell-v1",
            "--pcts",
            "50",
            "--widths",
            "20",
        ],
    )

    try:
        result = runner.main()
    except SystemExit as error:
        return_code = error.code if isinstance(error.code, int) else 1
        message = str(error)
    except (RuntimeError, ValueError) as error:
        return_code = 1
        message = str(error)
    else:
        return_code = 0 if result is None else int(result)
        message = ""
    captured = capsys.readouterr()
    diagnostic = " ".join((message, captured.out, captured.err)).lower()

    assert return_code != 0
    assert "reduc" in diagnostic
    assert "hierarch" in diagnostic or "managed" in diagnostic
    assert not (output_root / "results.json").exists()


@pytest.mark.parametrize(
    ("n_boot", "min_seeds", "message"),
    [
        (199, 10, "at least 200 bootstrap"),
        (200, 9, "at least 10 independent"),
    ],
)
def test_managed_cli_policy_rejects_exploratory_sample_sizes(
    n_boot: int,
    min_seeds: int,
    message: str,
) -> None:
    with pytest.raises(ValueError, match=message):
        runner._production_estimator_settings(n_boot, 2, min_seeds)


def test_managed_cli_policy_accepts_documented_minimums() -> None:
    settings = runner._production_estimator_settings(200, 2, 10)

    assert settings["n_boot"] == 200
    assert settings["min_seeds"] == 10


def test_cached_cell_accepts_exact_identity_and_complete_payload(tmp_path: Path) -> None:
    trace_root = tmp_path / "traces"
    _write_reduced_cell(trace_root)
    identity = _production_identity(trace_root)
    path = tmp_path / "analysis" / "cell.json"
    _write_cached_cell(path, identity)

    observed = _load_cached_cell(path, identity)

    assert observed is not None
    assert observed["growth_window_beta"] == pytest.approx(0.33)


def test_cached_cell_accepts_defined_meakin_slope_with_undefined_stderr(
    tmp_path: Path,
) -> None:
    trace_root = tmp_path / "traces"
    _write_reduced_cell(trace_root)
    identity = _production_identity(trace_root)
    path = tmp_path / "analysis" / "cell.json"
    cell = _cached_cell()
    cell["meakin_window2"] = {"slope": 0.0, "se": None}
    _write_cached_cell(path, identity, cell)

    observed = _load_cached_cell(path, identity)

    assert observed["meakin_window2"] == {"slope": 0.0, "se": None}


def test_cached_cell_binds_reported_seed_count_to_input_inventory(
    tmp_path: Path,
) -> None:
    trace_root = tmp_path / "traces"
    _write_reduced_cell(trace_root)
    identity = _production_identity(trace_root)
    path = tmp_path / "analysis" / "cell.json"
    cell = _cached_cell()
    cell["n_seeds"] = 999
    _write_cached_cell(path, identity, cell)

    with pytest.raises(AnalysisArtifactValidationError, match="seed inventory"):
        _load_cached_cell(path, identity)


def test_cached_cell_binds_point_count_to_sampling_policy(tmp_path: Path) -> None:
    trace_root = tmp_path / "traces"
    _write_reduced_cell(trace_root)
    identity = _production_identity(trace_root)
    path = tmp_path / "analysis" / "cell.json"
    cell = _cached_cell()
    cell["analysis_point_count"] = 3
    _write_cached_cell(path, identity, cell)

    with pytest.raises(AnalysisArtifactValidationError, match="sampling policy"):
        _load_cached_cell(path, identity)


@pytest.mark.parametrize(
    "dimension",
    [
        "cell",
        "input",
        "n-boot",
        "n-eval",
        "min-seeds",
        "percentage-convention",
        "software",
        "rng",
    ],
    ids=[
        "cell",
        "input",
        "n-boot",
        "n-eval",
        "min-seeds",
        "percentage-convention",
        "software",
        "rng",
    ],
)
def test_cached_cell_rejects_every_identity_mismatch(
    tmp_path: Path,
    dimension: str,
) -> None:
    trace_root = tmp_path / "traces"
    _write_reduced_cell(trace_root)
    cached_identity = _production_identity(trace_root)
    path = tmp_path / "analysis" / "cell.json"
    _write_cached_cell(path, cached_identity)
    if dimension == "cell":
        _write_reduced_cell(trace_root, width=30)
        expected_identity = _production_identity(trace_root, width=30)
    elif dimension == "input":
        _write_reduced_cell(trace_root, marker=77.0)
        expected_identity = _production_identity(trace_root)
    elif dimension == "n-boot":
        expected_identity = _production_identity(trace_root, n_boot=201)
    elif dimension == "n-eval":
        expected_identity = _production_identity(trace_root, n_eval=4)
    elif dimension == "min-seeds":
        expected_identity = _production_identity(trace_root, min_seeds=3)
    elif dimension == "percentage-convention":
        expected_identity = _production_identity(
            trace_root, percentage_convention="nonsticky-fraction"
        )
    elif dimension == "software":
        expected_identity = _production_identity(
            trace_root, software_sha256="4" * 64
        )
    elif dimension == "rng":
        expected_identity = _production_identity(trace_root, root_seed=43)
    else:  # pragma: no cover - guarded by the parametrization above
        raise AssertionError(f"unhandled identity dimension: {dimension}")

    assert cached_identity["sha256"] != expected_identity["sha256"]
    _assert_cache_rejected(path, expected_identity)


@pytest.mark.parametrize(
    "payload",
    [
        b'{"analysis_identity":',
        b'{"analysis_identity":{},"analysis_identity":{}}\n',
        b'{"analysis_identity":{},"growth_window_beta":NaN}\n',
    ],
    ids=["truncated", "duplicate-key", "nonfinite"],
)
def test_cached_cell_rejects_corrupt_json(
    tmp_path: Path,
    payload: bytes,
) -> None:
    path = tmp_path / "cell.json"
    identity = _base_identity()
    _write_cached_cell(path, identity)
    _replace_managed_payload(path, payload)

    _assert_cache_rejected(path, identity)


def test_cached_cell_requires_complete_numeric_payload(tmp_path: Path) -> None:
    cell = _cached_cell()
    del cell["slope_hi"]
    path = tmp_path / "cell.json"
    _write_cached_cell(path, _base_identity(), cell)

    _assert_cache_rejected(path, _base_identity())


def test_aggregate_uses_only_the_exact_requested_percentages(tmp_path: Path) -> None:
    requested_identity = _base_identity()
    _write_cached_cell(
        Path(runner._cell_path(str(tmp_path), 50, 20)),
        requested_identity,
    )
    stale_identity = _base_identity(percentage=90)
    stale_cell = _cached_cell(percentage=90)
    _write_cached_cell(
        Path(runner._cell_path(str(tmp_path), 90, 20)),
        stale_identity,
        stale_cell,
    )
    stale_width_identity = _base_identity(width=30)
    stale_width_cell = _cached_cell(width=30)
    _write_cached_cell(
        Path(runner._cell_path(str(tmp_path), 50, 30)),
        stale_width_identity,
        stale_width_cell,
    )

    result = runner.aggregate_results(
        str(tmp_path),
        percentages=[50],
        widths=[20],
        expected_cell_identities={(50, 20): requested_identity},
    )

    assert set(result) == {"50"}
    assert set(result["50"]["cells"]) == {"20"}


def test_aggregate_rejects_missing_requested_cell(tmp_path: Path) -> None:
    with pytest.raises(
        (AnalysisArtifactValidationError, ValueError),
        match="missing|expected|cell|manifest",
    ):
        runner.aggregate_results(
            str(tmp_path),
            percentages=[50],
            widths=[20],
            expected_cell_identities={(50, 20): _base_identity()},
        )


def test_aggregate_rejects_mixed_cell_identity(tmp_path: Path) -> None:
    cached_identity = _base_identity()
    _write_cached_cell(
        Path(runner._cell_path(str(tmp_path), 50, 20)),
        cached_identity,
    )

    with pytest.raises(
        (AnalysisArtifactValidationError, ValueError),
        match="identity|stale|mismatch|current request",
    ):
        runner.aggregate_results(
            str(tmp_path),
            percentages=[50],
            widths=[20],
            expected_cell_identities={
                (50, 20): _base_identity(input_sha256="9" * 64)
            },
        )


def test_aggregate_rejects_identity_context_that_disagrees_with_grid_key(
    tmp_path: Path,
) -> None:
    wrong_identity = _base_identity(percentage=90, width=30)
    _write_cached_cell(
        Path(runner._cell_path(str(tmp_path), 50, 20)),
        wrong_identity,
        _cached_cell(percentage=90, width=30),
    )

    with pytest.raises(
        (AnalysisArtifactValidationError, ValueError),
        match="context|coordinate|grid|percentage|width|identity",
    ):
        runner.aggregate_results(
            str(tmp_path),
            percentages=[50],
            widths=[20],
            expected_cell_identities={(50, 20): wrong_identity},
        )


def test_atomic_json_is_finite_canonical_and_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"
    value = {
        "z": np.float64(3.0),
        "a": np.asarray([np.int64(1), np.nan]),
        "nested": {"b": np.bool_(True)},
    }

    runner._atomic_write_json(str(first), value)
    runner._atomic_write_json(str(second), deepcopy(value))

    expected = b'{"a":[1.0,null],"nested":{"b":true},"z":3.0}\n'
    assert first.read_bytes() == expected
    assert second.read_bytes() == expected
    assert b"NaN" not in first.read_bytes()


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_atomic_json_normalizes_nonfinite_estimates_to_null(
    tmp_path: Path,
    nonfinite: float,
) -> None:
    path = tmp_path / "result.json"

    runner._atomic_write_json(str(path), {"estimate": nonfinite})

    assert path.read_bytes() == b'{"estimate":null}\n'
    assert b"NaN" not in path.read_bytes()
    assert b"Infinity" not in path.read_bytes()
    assert not list(tmp_path.glob(".result.json.*.tmp"))
    assert not (tmp_path / "result.json.tmp").exists()


def test_derived_publication_revalidates_claimed_child_identity(tmp_path: Path) -> None:
    out_dir = tmp_path / "analysis"
    identity_a = _base_identity()
    cell_path = Path(runner._cell_path(str(out_dir), 50, 20))
    _write_cached_cell(cell_path, identity_a)
    results = runner.aggregate_results(
        str(out_dir), [50], [20], {(50, 20): identity_a}
    )
    identity_b = _base_identity(input_sha256="9" * 64)
    _write_cached_cell(cell_path, identity_b)

    with pytest.raises(AnalysisArtifactValidationError, match="identity|current"):
        runner._publish_derived_results(
            out_dir=str(out_dir),
            percentages=[50],
            widths=[20],
            percentage_convention="sticky-fraction",
            model_profile="piece-19-one-cell-v1",
            results=results,
            cell_identities={(50, 20): identity_a},
            software=_test_software_identity(),
        )


def test_current_results_recompute_and_validate_all_dependencies(tmp_path: Path) -> None:
    out_dir = tmp_path / "analysis"
    identity_a = _base_identity()
    cell_path = Path(runner._cell_path(str(out_dir), 50, 20))
    _write_cached_cell(cell_path, identity_a)
    results = runner.aggregate_results(
        str(out_dir), [50], [20], {(50, 20): identity_a}
    )
    software = _test_software_identity()
    runner._publish_derived_results(
        out_dir=str(out_dir),
        percentages=[50],
        widths=[20],
        percentage_convention="sticky-fraction",
        model_profile="piece-19-one-cell-v1",
        results=results,
        cell_identities={(50, 20): identity_a},
        software=software,
    )

    observed = runner.load_current_results(
        out_dir=str(out_dir),
        percentages=[50],
        widths=[20],
        percentage_convention="sticky-fraction",
        model_profile="piece-19-one-cell-v1",
        cell_identities={(50, 20): identity_a},
        software=software,
    )
    assert observed == results

    identity_b = _base_identity(input_sha256="8" * 64)
    _write_cached_cell(cell_path, identity_b)
    with pytest.raises(AnalysisArtifactValidationError, match="identity|current"):
        runner.load_current_results(
            out_dir=str(out_dir),
            percentages=[50],
            widths=[20],
            percentage_convention="sticky-fraction",
            model_profile="piece-19-one-cell-v1",
            cell_identities={(50, 20): identity_a},
            software=software,
        )


def test_failed_rerun_withdraws_old_derived_commit_markers(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_root = tmp_path / "traces"
    _write_reduced_cell(trace_root)
    out_dir = tmp_path / "analysis"
    identity = _base_identity()
    results_path = out_dir / "results.json"
    per_pct_path = Path(runner._per_pct_path(str(out_dir), 50))
    write_json_artifact(results_path, {"old": True}, identity)
    write_json_artifact(per_pct_path, {"old": True}, identity)
    for name in ("local_slope_pct50.png", "multi_L_extrapolation_pct50.png"):
        (out_dir / name).write_bytes(b"old plot")

    def fail_cell(**_kwargs):
        raise AnalysisArtifactValidationError("stale cell")

    monkeypatch.setattr(runner, "_compute_or_load_cell", fail_cell)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_kpz_analysis",
            "--trace-root",
            str(trace_root),
            "--input-layout",
            "reduced",
            "--percentage-convention",
            "sticky-fraction",
            "--model-profile",
            "piece-19-one-cell-v1",
            "--out-dir",
            str(out_dir),
            "--pcts",
            "50",
            "--widths",
            "20",
            "--resume",
        ],
    )

    with pytest.raises(SystemExit, match="failed closed"):
        runner.main()

    assert not analysis_artifact_paths(results_path).manifest.exists()
    assert not analysis_artifact_paths(per_pct_path).manifest.exists()
    assert not (out_dir / "local_slope_pct50.png").exists()
    assert not (out_dir / "multi_L_extrapolation_pct50.png").exists()


def test_late_failure_withdraws_diagnostic_written_by_failed_generation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trace_root = tmp_path / "traces"
    _write_reduced_cell(trace_root)
    out_dir = tmp_path / "analysis"
    plot_path = out_dir / "local_slope_pct50.png"

    monkeypatch.setattr(
        runner,
        "_compute_or_load_cell",
        lambda **_kwargs: (_cached_cell(), _base_identity(), False),
    )
    monkeypatch.setattr(
        runner,
        "aggregate_results",
        lambda *_args, **_kwargs: {"50": {}},
    )

    def write_diagnostic(_pct, _per_L_data, _widths, destination, **_kwargs):
        Path(destination, plot_path.name).write_bytes(b"uncommitted diagnostic")

    monkeypatch.setattr(runner, "plot_local_slopes", write_diagnostic)
    monkeypatch.setattr(
        runner,
        "_summarize_percentage",
        lambda *_args, **_kwargs: ({}, [], None),
    )

    def fail_publication(**_kwargs):
        assert plot_path.exists()
        raise AnalysisArtifactValidationError("late publication failure")

    monkeypatch.setattr(runner, "_publish_derived_results", fail_publication)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_kpz_analysis",
            "--trace-root",
            str(trace_root),
            "--input-layout",
            "reduced",
            "--percentage-convention",
            "sticky-fraction",
            "--model-profile",
            "piece-19-one-cell-v1",
            "--out-dir",
            str(out_dir),
            "--pcts",
            "50",
            "--widths",
            "20",
        ],
    )

    with pytest.raises(SystemExit, match="late publication failure"):
        runner.main()

    assert not plot_path.exists()
    assert not analysis_artifact_paths(out_dir / "results.json").manifest.exists()
    assert not analysis_artifact_paths(
        Path(runner._per_pct_path(str(out_dir), 50))
    ).manifest.exists()
