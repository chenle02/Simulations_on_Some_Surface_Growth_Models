"""Exact scalar multi-arm trajectories for the PRE one-cell study.

This provisional explicit-submodule surface composes the certified shared
one-cell selector and the certified three-law boundary transition.  It folds
only exact integer trajectory projections and retains no event, contact, RNG,
transition, or height-history tape.  It performs no compiled execution,
persistence, configuration, legacy dispatch, or acquisition routing.
"""

from __future__ import annotations

from dataclasses import dataclass

from .one_cell_boundary import (
    OneCellBoundaryLaw,
    OneCellBoundaryTransition,
    OneCellCausalSide,
    transition_one_cell_boundary,
)
from .one_cell_coupling import OneCellCoupledEventSelection, select_one_cell_coupled_event

__all__ = [
    "OneCellScalarArmAccumulator",
    "OneCellScalarTrajectory",
    "start_one_cell_scalar_trajectory",
    "advance_one_cell_scalar_chunk",
]

_U64_MODULUS = 1 << 64
_U64_MAX = _U64_MODULUS - 1
_U128_MODULUS = 1 << 128
_U128_MAX = _U128_MODULUS - 1
_MIN_WIDTH = 3
_MAX_WIDTH = 1024
_THRESHOLDS = (0, 1, 2, 5, 10, 25, 50, 100)

# Capture the certified authority objects once.  The private delegate defaults
# below make later rebinding of imported aliases unable to redirect execution.
_BOUNDARY_LAW_TYPE = OneCellBoundaryLaw
_BOUNDARY_TRANSITION_TYPE = OneCellBoundaryTransition
_CAUSAL_SIDE_TYPE = OneCellCausalSide
_COUPLED_SELECTION_TYPE = OneCellCoupledEventSelection
_CERTIFIED_SELECT_EVENT = select_one_cell_coupled_event
_CERTIFIED_BOUNDARY_TRANSITION = transition_one_cell_boundary

_PERIODIC = _BOUNDARY_LAW_TYPE.PERIODIC
_HARD_WALL_LEGACY = _BOUNDARY_LAW_TYPE.HARD_WALL_LEGACY_ASYMMETRIC
_HARD_WALL_CORRECTED = _BOUNDARY_LAW_TYPE.HARD_WALL_REFLECTION_SYMMETRIC
_BOUNDARY_LAWS = (_PERIODIC, _HARD_WALL_LEGACY, _HARD_WALL_CORRECTED)

_CAUSAL_ORDER = (
    _CAUSAL_SIDE_TYPE.NONE,
    _CAUSAL_SIDE_TYPE.LEFT,
    _CAUSAL_SIDE_TYPE.RIGHT,
    _CAUSAL_SIDE_TYPE.BOTH,
)


def _assert_contract_integrity(
    *,
    _boundary_law_type: object = _BOUNDARY_LAW_TYPE,
    _boundary_transition_type: object = _BOUNDARY_TRANSITION_TYPE,
    _causal_side_type: object = _CAUSAL_SIDE_TYPE,
    _coupled_selection_type: object = _COUPLED_SELECTION_TYPE,
    _certified_selector: object = _CERTIFIED_SELECT_EVENT,
    _certified_transition: object = _CERTIFIED_BOUNDARY_TRANSITION,
    _periodic: object = _PERIODIC,
    _hard_wall_legacy: object = _HARD_WALL_LEGACY,
    _hard_wall_corrected: object = _HARD_WALL_CORRECTED,
    _causal_order: object = _CAUSAL_ORDER,
) -> None:
    """Fail closed if any private frozen authority has been rebound."""

    if (
        type(_U64_MODULUS) is not int
        or _U64_MODULUS != 1 << 64
        or type(_U64_MAX) is not int
        or _U64_MAX != (1 << 64) - 1
        or type(_U128_MODULUS) is not int
        or _U128_MODULUS != 1 << 128
        or type(_U128_MAX) is not int
        or _U128_MAX != (1 << 128) - 1
    ):
        raise AssertionError("unsigned scalar bounds do not match the frozen protocol")
    if type(_MIN_WIDTH) is not int or _MIN_WIDTH != 3 or type(_MAX_WIDTH) is not int or _MAX_WIDTH != 1024:
        raise AssertionError("trajectory width bounds do not match the frozen protocol")
    if (
        type(_THRESHOLDS) is not tuple
        or _THRESHOLDS != (0, 1, 2, 5, 10, 25, 50, 100)
        or any(type(threshold) is not int for threshold in _THRESHOLDS)
    ):
        raise AssertionError("trajectory thresholds do not match the frozen protocol")
    if (
        _BOUNDARY_LAW_TYPE is not _boundary_law_type
        or _BOUNDARY_TRANSITION_TYPE is not _boundary_transition_type
        or _CAUSAL_SIDE_TYPE is not _causal_side_type
        or _COUPLED_SELECTION_TYPE is not _coupled_selection_type
        or _CERTIFIED_SELECT_EVENT is not _certified_selector
        or _CERTIFIED_BOUNDARY_TRANSITION is not _certified_transition
    ):
        raise AssertionError("captured upstream authority objects have been rebound")
    if (
        _PERIODIC is not _periodic
        or _HARD_WALL_LEGACY is not _hard_wall_legacy
        or _HARD_WALL_CORRECTED is not _hard_wall_corrected
        or type(_BOUNDARY_LAWS) is not tuple
        or len(_BOUNDARY_LAWS) != 3
        or any(
            actual is not expected
            for actual, expected in zip(_BOUNDARY_LAWS, (_periodic, _hard_wall_legacy, _hard_wall_corrected))
        )
    ):
        raise AssertionError("boundary identities do not match the frozen protocol")
    if (
        _CAUSAL_ORDER is not _causal_order
        or type(_CAUSAL_ORDER) is not tuple
        or len(_CAUSAL_ORDER) != 4
        or any(
            actual is not expected
            for actual, expected in zip(
                _CAUSAL_ORDER,
                (
                    _causal_side_type.NONE,
                    _causal_side_type.LEFT,
                    _causal_side_type.RIGHT,
                    _causal_side_type.BOTH,
                ),
            )
        )
    ):
        raise AssertionError("causal-bin order does not match the frozen protocol")


def _require_plain_int(value: object, *, label: str) -> int:
    if type(value) is not int:
        raise TypeError(f"{label} must be a built-in integer")
    return value


def _require_uint(value: object, *, maximum: int, label: str) -> int:
    result = _require_plain_int(value, label=label)
    if not 0 <= result <= maximum:
        raise ValueError(f"{label} must lie in [0, {maximum}]")
    return result


def _require_width(value: object) -> int:
    width = _require_plain_int(value, label="width")
    if not _MIN_WIDTH <= width <= _MAX_WIDTH:
        raise ValueError(f"width must lie in [{_MIN_WIDTH}, {_MAX_WIDTH}]")
    return width


def _require_boundary_law(value: object) -> OneCellBoundaryLaw:
    if type(value) is not _BOUNDARY_LAW_TYPE:
        raise TypeError("boundary_law must be a OneCellBoundaryLaw")
    if value not in _BOUNDARY_LAWS:  # pragma: no cover - exact enum type closes this branch
        raise ValueError("boundary_law is not a frozen PRE one-cell boundary")
    return value


def _require_threshold(value: object) -> int:
    threshold = _require_plain_int(value, label="threshold")
    if threshold not in _THRESHOLDS:
        raise ValueError("threshold must be one of the eight frozen PRE thresholds")
    return threshold


def _snapshot_uint_tuple(value: object, *, length: int, label: str) -> tuple[int, ...]:
    if type(value) is not tuple:
        raise TypeError(f"{label} must be a built-in tuple")
    if len(value) != length:
        raise ValueError(f"{label} must contain exactly {length} entries")
    return tuple(_require_uint(item, maximum=_U64_MAX, label=f"{label} entry") for item in value)


def _snapshot_heights(value: object, *, event_count: int) -> tuple[int, ...]:
    if type(value) is not tuple:
        raise TypeError("heights must be a built-in tuple")
    if not _MIN_WIDTH <= len(value) <= _MAX_WIDTH:
        raise ValueError(f"heights must contain between {_MIN_WIDTH} and {_MAX_WIDTH} columns")
    heights: list[int] = []
    for height in value:
        copied = _require_uint(height, maximum=_U64_MAX, label="height")
        if copied > event_count:
            raise ValueError("each height must not exceed event_count")
        heights.append(copied)
    return tuple(heights)


def _snapshot_equality_counts(value: object) -> tuple[tuple[int, ...], tuple[int, ...]]:
    if type(value) is not tuple:
        raise TypeError("endpoint_equality_mask_counts must be a built-in tuple")
    if len(value) != 2:
        raise ValueError("endpoint_equality_mask_counts must contain exactly two rows")
    return (
        _snapshot_uint_tuple(value[0], length=8, label="endpoint-false equality row"),
        _snapshot_uint_tuple(value[1], length=8, label="endpoint-true equality row"),
    )


def _snapshot_histogram(value: object) -> tuple[tuple[int, int], ...]:
    if type(value) is not tuple:
        raise TypeError("gap_histogram must be a built-in tuple")
    result: list[tuple[int, int]] = []
    previous_key = -1
    for pair in value:
        if type(pair) is not tuple:
            raise TypeError("each gap_histogram entry must be a built-in tuple")
        if len(pair) != 2:
            raise ValueError("each gap_histogram entry must contain a gap and count")
        gap = _require_uint(pair[0], maximum=_U64_MAX, label="histogram gap")
        count = _require_uint(pair[1], maximum=_U64_MAX, label="histogram count")
        if count == 0:
            raise ValueError("gap_histogram counts must be positive")
        if gap <= previous_key:
            raise ValueError("gap_histogram gaps must be strictly increasing")
        result.append((gap, count))
        previous_key = gap
    return tuple(result)


def _validate_protocol_products(*, width: int, event_count: int) -> None:
    if width * event_count >= _U64_MODULUS:
        raise ValueError("width * event_count must be less than 2**64")
    if width * event_count * event_count >= _U128_MODULUS:
        raise ValueError("width * event_count**2 must be less than 2**128")


@dataclass(frozen=True, slots=True)
class OneCellScalarArmAccumulator:
    """Structurally certified exact projections for one sticky-threshold arm.

    Direct construction authenticates the retained integer projections, not
    the claimed Philox or event history.  Procedural provenance applies to
    records returned by this module's start-and-contiguous-advance path.
    """

    boundary_law: OneCellBoundaryLaw
    threshold: int
    heights: tuple[int, ...]
    event_count: int
    height_sum: int
    height_square_sum: int
    void_volume: int
    endpoint_selected_count: int
    positive_gap_trigger_count: int
    gap_sum: int
    maximum_gap: int
    causal_counts: tuple[int, int, int, int]
    causal_gap_sums: tuple[int, int, int, int]
    endpoint_equality_mask_counts: tuple[tuple[int, ...], tuple[int, ...]]
    gap_histogram: tuple[tuple[int, int], ...]
    seam_equality_count: int | None

    def __post_init__(self) -> None:
        _assert_contract_integrity()
        boundary_law = _require_boundary_law(self.boundary_law)
        threshold = _require_threshold(self.threshold)
        event_count = _require_uint(self.event_count, maximum=_U64_MAX, label="event_count")
        heights = _snapshot_heights(self.heights, event_count=event_count)
        height_sum = _require_uint(self.height_sum, maximum=_U64_MAX, label="height_sum")
        height_square_sum = _require_uint(
            self.height_square_sum,
            maximum=_U128_MAX,
            label="height_square_sum",
        )
        void_volume = _require_uint(self.void_volume, maximum=_U64_MAX, label="void_volume")
        endpoint_selected_count = _require_uint(
            self.endpoint_selected_count,
            maximum=_U64_MAX,
            label="endpoint_selected_count",
        )
        positive_gap_trigger_count = _require_uint(
            self.positive_gap_trigger_count,
            maximum=_U64_MAX,
            label="positive_gap_trigger_count",
        )
        gap_sum = _require_uint(self.gap_sum, maximum=_U64_MAX, label="gap_sum")
        maximum_gap = _require_uint(self.maximum_gap, maximum=_U64_MAX, label="maximum_gap")
        causal_counts = _snapshot_uint_tuple(self.causal_counts, length=4, label="causal_counts")
        causal_gap_sums = _snapshot_uint_tuple(
            self.causal_gap_sums,
            length=4,
            label="causal_gap_sums",
        )
        equality_counts = _snapshot_equality_counts(self.endpoint_equality_mask_counts)
        histogram = _snapshot_histogram(self.gap_histogram)

        if sum(heights) != height_sum:
            raise ValueError("height_sum must equal the sum of heights")
        if sum(height * height for height in heights) != height_square_sum:
            raise ValueError("height_square_sum must equal the sum of squared heights")
        if void_volume != height_sum - event_count:
            raise ValueError("void_volume must equal height_sum - event_count")
        if gap_sum != void_volume:
            raise ValueError("gap_sum must equal void_volume")
        if len(heights) * height_square_sum - height_sum * height_sum < 0:
            raise ValueError("the exact roughness numerator must be nonnegative")

        if positive_gap_trigger_count > endpoint_selected_count or endpoint_selected_count > event_count:
            raise ValueError("trigger and endpoint counts must satisfy trigger <= endpoint <= event_count")

        false_row, true_row = equality_counts
        if false_row[0] != 0 or true_row[0] != 0:
            raise ValueError("equality mask zero is unreachable in either endpoint stratum")
        if sum(false_row) + sum(true_row) != event_count:
            raise ValueError("equality-mask counts must total event_count")
        if sum(true_row) != endpoint_selected_count:
            raise ValueError("the endpoint-true equality row must total endpoint_selected_count")

        if sum(causal_counts) != event_count:
            raise ValueError("causal_counts must total event_count")
        if causal_counts[0] != event_count - positive_gap_trigger_count:
            raise ValueError("the none causal count must equal event_count - trigger count")
        if sum(causal_counts[1:]) != positive_gap_trigger_count:
            raise ValueError("non-none causal counts must total the trigger count")
        if causal_gap_sums[0] != 0:
            raise ValueError("the none causal gap sum must be zero")
        if sum(causal_gap_sums) != void_volume:
            raise ValueError("causal_gap_sums must total void_volume")

        if event_count == 0:
            if histogram:
                raise ValueError("gap_histogram must be empty exactly at event_count zero")
            if maximum_gap != 0:
                raise ValueError("maximum_gap must be zero at event_count zero")
        else:
            if not histogram or histogram[0][0] != 0:
                raise ValueError("a nonempty prefix must contain a positive zero-gap bin")
            if sum(count for _, count in histogram) != event_count:
                raise ValueError("gap_histogram counts must total event_count")
            if sum(gap * count for gap, count in histogram) != void_volume:
                raise ValueError("the gap_histogram weighted sum must equal void_volume")
            if sum(count for gap, count in histogram if gap > 0) != positive_gap_trigger_count:
                raise ValueError("positive gap bins must total the trigger count")
            if histogram[-1][0] != maximum_gap:
                raise ValueError("maximum_gap must equal the final histogram key")

        if threshold == 0 and (
            endpoint_selected_count != 0
            or positive_gap_trigger_count != 0
            or void_volume != 0
            or height_sum != event_count
        ):
            raise ValueError("the zero-percent arm must remain the exact random-deposition control")
        if threshold == 100 and endpoint_selected_count != event_count:
            raise ValueError("the one-hundred-percent arm must select every endpoint")

        if boundary_law is _PERIODIC:
            seam_equality_count = _require_uint(
                self.seam_equality_count,
                maximum=_U64_MAX,
                label="seam_equality_count",
            )
            if seam_equality_count > event_count:
                raise ValueError("periodic seam_equality_count must not exceed event_count")
        else:
            if self.seam_equality_count is not None:
                raise ValueError("hard-wall seam_equality_count must be None")
            seam_equality_count = None

        object.__setattr__(self, "boundary_law", boundary_law)
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "heights", heights)
        object.__setattr__(self, "event_count", event_count)
        object.__setattr__(self, "height_sum", height_sum)
        object.__setattr__(self, "height_square_sum", height_square_sum)
        object.__setattr__(self, "void_volume", void_volume)
        object.__setattr__(self, "endpoint_selected_count", endpoint_selected_count)
        object.__setattr__(self, "positive_gap_trigger_count", positive_gap_trigger_count)
        object.__setattr__(self, "gap_sum", gap_sum)
        object.__setattr__(self, "maximum_gap", maximum_gap)
        object.__setattr__(self, "causal_counts", causal_counts)
        object.__setattr__(self, "causal_gap_sums", causal_gap_sums)
        object.__setattr__(self, "endpoint_equality_mask_counts", equality_counts)
        object.__setattr__(self, "gap_histogram", histogram)
        object.__setattr__(self, "seam_equality_count", seam_equality_count)

    @property
    def width(self) -> int:
        """Return the substrate width."""

        return len(self.heights)

    @property
    def roughness_numerator(self) -> int:
        """Return the exact unnormalized width-squared roughness numerator."""

        return self.width * self.height_square_sum - self.height_sum * self.height_sum


_ARM_TYPE = OneCellScalarArmAccumulator


def _snapshot_arm(value: object, *, label: str) -> OneCellScalarArmAccumulator:
    _assert_contract_integrity()
    _assert_record_type_integrity()
    if type(value) is not _ARM_TYPE:
        raise TypeError(f"{label} must be a OneCellScalarArmAccumulator")
    try:
        return _ARM_TYPE(
            boundary_law=value.boundary_law,
            threshold=value.threshold,
            heights=value.heights,
            event_count=value.event_count,
            height_sum=value.height_sum,
            height_square_sum=value.height_square_sum,
            void_volume=value.void_volume,
            endpoint_selected_count=value.endpoint_selected_count,
            positive_gap_trigger_count=value.positive_gap_trigger_count,
            gap_sum=value.gap_sum,
            maximum_gap=value.maximum_gap,
            causal_counts=value.causal_counts,
            causal_gap_sums=value.causal_gap_sums,
            endpoint_equality_mask_counts=value.endpoint_equality_mask_counts,
            gap_histogram=value.gap_histogram,
            seam_equality_count=value.seam_equality_count,
        )
    except AttributeError as error:
        raise TypeError(f"{label} must be fully initialized") from error


@dataclass(frozen=True, slots=True)
class OneCellScalarTrajectory:
    """Immutable exact scalar prefix shared by all eight PRE arms."""

    root_seed: int
    boundary_law: OneCellBoundaryLaw
    width: int
    event_count: int
    arms: tuple[OneCellScalarArmAccumulator, ...]

    def __post_init__(self) -> None:
        _assert_contract_integrity()
        _assert_record_type_integrity()
        root_seed = _require_uint(self.root_seed, maximum=_U128_MAX, label="root_seed")
        boundary_law = _require_boundary_law(self.boundary_law)
        width = _require_width(self.width)
        event_count = _require_uint(self.event_count, maximum=_U64_MAX, label="event_count")
        _validate_protocol_products(width=width, event_count=event_count)

        if type(self.arms) is not tuple:
            raise TypeError("arms must be a built-in tuple")
        if len(self.arms) != len(_THRESHOLDS):
            raise ValueError("arms must contain exactly the eight frozen thresholds")
        arms = tuple(_snapshot_arm(arm, label=f"arm {index}") for index, arm in enumerate(self.arms))

        for index, (arm, threshold) in enumerate(zip(arms, _THRESHOLDS)):
            if arm.boundary_law is not boundary_law:
                raise ValueError(f"arm {index} boundary_law must equal the trajectory boundary_law")
            if arm.threshold != threshold:
                raise ValueError("arms must appear in the frozen threshold order")
            if arm.width != width:
                raise ValueError(f"arm {index} width must equal the trajectory width")
            if arm.event_count != event_count:
                raise ValueError(f"arm {index} event_count must equal the trajectory event_count")

        for lower, upper in zip(arms, arms[1:]):
            if lower.endpoint_selected_count > upper.endpoint_selected_count:
                raise ValueError("endpoint counts must be nondecreasing across thresholds")
            if any(lower_height > upper_height for lower_height, upper_height in zip(lower.heights, upper.heights)):
                raise ValueError("column heights must be nondecreasing across thresholds")

        object.__setattr__(self, "root_seed", root_seed)
        object.__setattr__(self, "boundary_law", boundary_law)
        object.__setattr__(self, "width", width)
        object.__setattr__(self, "event_count", event_count)
        object.__setattr__(self, "arms", arms)


_TRAJECTORY_TYPE = OneCellScalarTrajectory


def _assert_record_type_integrity(
    *,
    _arm_type: object = _ARM_TYPE,
    _trajectory_type: object = _TRAJECTORY_TYPE,
) -> None:
    if _ARM_TYPE is not _arm_type or _TRAJECTORY_TYPE is not _trajectory_type:
        raise AssertionError("captured Slice 5 record types have been rebound")


def _snapshot_trajectory(value: object) -> OneCellScalarTrajectory:
    _assert_contract_integrity()
    _assert_record_type_integrity()
    if type(value) is not _TRAJECTORY_TYPE:
        raise TypeError("trajectory must be a OneCellScalarTrajectory")
    try:
        return _TRAJECTORY_TYPE(
            root_seed=value.root_seed,
            boundary_law=value.boundary_law,
            width=value.width,
            event_count=value.event_count,
            arms=value.arms,
        )
    except AttributeError as error:
        raise TypeError("trajectory must be fully initialized") from error


def _validate_stop(trajectory: OneCellScalarTrajectory, stop_event_ordinal: object) -> int:
    _assert_contract_integrity()
    _assert_record_type_integrity()
    stop = _require_uint(stop_event_ordinal, maximum=_U64_MAX, label="stop_event_ordinal")
    if stop < trajectory.event_count:
        raise ValueError("stop_event_ordinal must not precede trajectory.event_count")
    _validate_protocol_products(width=trajectory.width, event_count=stop)
    return stop


def _snapshot_delegated_selection(
    value: object,
    *,
    root_seed: int,
    event_ordinal: int,
    width: int,
) -> tuple[int, int]:
    _assert_contract_integrity()
    _assert_record_type_integrity()
    if type(value) is not _COUPLED_SELECTION_TYPE:
        raise AssertionError("the coupled selector returned an invalid record type")
    try:
        selection = _COUPLED_SELECTION_TYPE(
            root_seed=value.root_seed,
            event_ordinal=value.event_ordinal,
            width=value.width,
            launch=value.launch,
            contact=value.contact,
        )
    except (AttributeError, TypeError, ValueError, AssertionError) as error:
        raise AssertionError("the coupled selector returned a malformed record") from error
    if selection.root_seed != root_seed or selection.event_ordinal != event_ordinal or selection.width != width:
        raise AssertionError("the coupled selector returned a record for a different request")
    return selection.launch.draw.value, selection.contact.draw.value


def _snapshot_delegated_transition(
    value: object,
    *,
    boundary_law: OneCellBoundaryLaw,
    pre_heights: tuple[int, ...],
    launch_x: int,
    sticky_endpoint_selected: bool,
) -> OneCellBoundaryTransition:
    _assert_contract_integrity()
    _assert_record_type_integrity()
    if type(value) is not _BOUNDARY_TRANSITION_TYPE:
        raise AssertionError("the boundary delegate returned an invalid record type")
    try:
        transition = _BOUNDARY_TRANSITION_TYPE(
            boundary_law=value.boundary_law,
            pre_heights=value.pre_heights,
            post_heights=value.post_heights,
            launch_x=value.launch_x,
            sticky_endpoint_selected=value.sticky_endpoint_selected,
            left_pre_height=value.left_pre_height,
            launch_pre_height=value.launch_pre_height,
            right_pre_height=value.right_pre_height,
            left_neighbor_eligible=value.left_neighbor_eligible,
            right_neighbor_eligible=value.right_neighbor_eligible,
            launch_post_height=value.launch_post_height,
            delta_s=value.delta_s,
            delta_v=value.delta_v,
            delta_q=value.delta_q,
            positive_gap_trigger=value.positive_gap_trigger,
            causal_side=value.causal_side,
            equality_mask=value.equality_mask,
            seam_equality=value.seam_equality,
        )
    except (AttributeError, TypeError, ValueError, AssertionError, RuntimeError) as error:
        raise AssertionError("the boundary delegate returned a malformed record") from error
    if (
        transition.boundary_law is not boundary_law
        or transition.pre_heights != pre_heights
        or transition.launch_x != launch_x
        or transition.sticky_endpoint_selected is not sticky_endpoint_selected
    ):
        raise AssertionError("the boundary delegate returned a record for a different request")
    return transition


def _fold_selected_event(
    *,
    trajectory: OneCellScalarTrajectory,
    launch_x: int,
    contact_value: int,
    _transition_delegate: object = _CERTIFIED_BOUNDARY_TRANSITION,
) -> OneCellScalarTrajectory:
    _assert_contract_integrity()
    _assert_record_type_integrity()
    next_event_count = trajectory.event_count + 1
    updated_arms: list[OneCellScalarArmAccumulator] = []
    for arm in trajectory.arms:
        endpoint_selected = contact_value < arm.threshold
        delegated = _transition_delegate(
            boundary_law=trajectory.boundary_law,
            heights=arm.heights,
            launch_x=launch_x,
            sticky_endpoint_selected=endpoint_selected,
        )
        transition = _snapshot_delegated_transition(
            delegated,
            boundary_law=trajectory.boundary_law,
            pre_heights=arm.heights,
            launch_x=launch_x,
            sticky_endpoint_selected=endpoint_selected,
        )

        causal_index = _CAUSAL_ORDER.index(transition.causal_side)
        causal_counts = list(arm.causal_counts)
        causal_counts[causal_index] += 1
        causal_gap_sums = list(arm.causal_gap_sums)
        causal_gap_sums[causal_index] += transition.delta_v

        equality_counts = [list(row) for row in arm.endpoint_equality_mask_counts]
        equality_counts[int(endpoint_selected)][transition.equality_mask] += 1

        histogram = dict(arm.gap_histogram)
        histogram[transition.delta_v] = histogram.get(transition.delta_v, 0) + 1

        if trajectory.boundary_law is _PERIODIC:
            if type(transition.seam_equality) is not bool:  # pragma: no cover - transition recertification
                raise AssertionError("periodic transition must report seam applicability")
            if type(arm.seam_equality_count) is not int:  # pragma: no cover - arm recertification
                raise AssertionError("periodic arm must retain a seam count")
            seam_equality_count: int | None = arm.seam_equality_count + int(transition.seam_equality)
        else:
            if transition.seam_equality is not None:  # pragma: no cover - transition recertification
                raise AssertionError("hard-wall transition must report seam non-applicability")
            seam_equality_count = None

        updated_arms.append(
            _ARM_TYPE(
                boundary_law=trajectory.boundary_law,
                threshold=arm.threshold,
                heights=transition.post_heights,
                event_count=next_event_count,
                height_sum=arm.height_sum + transition.delta_s,
                height_square_sum=arm.height_square_sum + transition.delta_q,
                void_volume=arm.void_volume + transition.delta_v,
                endpoint_selected_count=arm.endpoint_selected_count + int(endpoint_selected),
                positive_gap_trigger_count=(arm.positive_gap_trigger_count + int(transition.positive_gap_trigger)),
                gap_sum=arm.gap_sum + transition.delta_v,
                maximum_gap=max(arm.maximum_gap, transition.delta_v),
                causal_counts=tuple(causal_counts),
                causal_gap_sums=tuple(causal_gap_sums),
                endpoint_equality_mask_counts=tuple(tuple(row) for row in equality_counts),
                gap_histogram=tuple(sorted(histogram.items())),
                seam_equality_count=seam_equality_count,
            )
        )

    return _TRAJECTORY_TYPE(
        root_seed=trajectory.root_seed,
        boundary_law=trajectory.boundary_law,
        width=trajectory.width,
        event_count=next_event_count,
        arms=tuple(updated_arms),
    )


def _advance_selected_event(
    *,
    trajectory: OneCellScalarTrajectory,
    launch_x: int,
    contact_value: int,
) -> OneCellScalarTrajectory:
    """Testable deterministic fold of one already-selected shared event."""

    _assert_contract_integrity()
    _assert_record_type_integrity()
    snapshot = _snapshot_trajectory(trajectory)
    selected_launch = _require_plain_int(launch_x, label="launch_x")
    if not 0 <= selected_launch < snapshot.width:
        raise ValueError("launch_x must lie in [0, trajectory.width)")
    selected_contact = _require_plain_int(contact_value, label="contact_value")
    if not 0 <= selected_contact < 100:
        raise ValueError("contact_value must lie in [0, 100)")
    _validate_stop(snapshot, snapshot.event_count + 1)
    return _fold_selected_event(
        trajectory=snapshot,
        launch_x=selected_launch,
        contact_value=selected_contact,
    )


def _advance_certified_event(
    trajectory: OneCellScalarTrajectory,
    event_ordinal: int,
    *,
    _selector_delegate: object = _CERTIFIED_SELECT_EVENT,
) -> OneCellScalarTrajectory:
    _assert_contract_integrity()
    _assert_record_type_integrity()
    delegated = _selector_delegate(
        root_seed=trajectory.root_seed,
        event_ordinal=event_ordinal,
        width=trajectory.width,
    )
    launch_x, contact_value = _snapshot_delegated_selection(
        delegated,
        root_seed=trajectory.root_seed,
        event_ordinal=event_ordinal,
        width=trajectory.width,
    )
    return _fold_selected_event(
        trajectory=trajectory,
        launch_x=launch_x,
        contact_value=contact_value,
    )


def start_one_cell_scalar_trajectory(
    *,
    root_seed: int,
    boundary_law: OneCellBoundaryLaw,
    width: int,
) -> OneCellScalarTrajectory:
    """Create the canonical all-zero scalar prefix for all eight PRE arms."""

    _assert_contract_integrity()
    _assert_record_type_integrity()
    root = _require_uint(root_seed, maximum=_U128_MAX, label="root_seed")
    law = _require_boundary_law(boundary_law)
    selected_width = _require_width(width)
    _validate_protocol_products(width=selected_width, event_count=0)

    arms = []
    for threshold in _THRESHOLDS:
        arms.append(
            _ARM_TYPE(
                boundary_law=law,
                threshold=threshold,
                heights=tuple(0 for _ in range(selected_width)),
                event_count=0,
                height_sum=0,
                height_square_sum=0,
                void_volume=0,
                endpoint_selected_count=0,
                positive_gap_trigger_count=0,
                gap_sum=0,
                maximum_gap=0,
                causal_counts=(0, 0, 0, 0),
                causal_gap_sums=(0, 0, 0, 0),
                endpoint_equality_mask_counts=((0, 0, 0, 0, 0, 0, 0, 0), (0, 0, 0, 0, 0, 0, 0, 0)),
                gap_histogram=(),
                seam_equality_count=0 if law is _PERIODIC else None,
            )
        )
    return _TRAJECTORY_TYPE(
        root_seed=root,
        boundary_law=law,
        width=selected_width,
        event_count=0,
        arms=tuple(arms),
    )


def advance_one_cell_scalar_chunk(
    *,
    trajectory: OneCellScalarTrajectory,
    stop_event_ordinal: int,
) -> OneCellScalarTrajectory:
    """Advance exactly ``[trajectory.event_count, stop_event_ordinal)``."""

    _assert_contract_integrity()
    _assert_record_type_integrity()
    result = _snapshot_trajectory(trajectory)
    stop = _validate_stop(result, stop_event_ordinal)
    for event_ordinal in range(result.event_count, stop):
        result = _advance_certified_event(result, event_ordinal)
    return result
