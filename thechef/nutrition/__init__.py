"""Pure nutrition math (no database, no HTTP): energy needs, macro targets, portions."""

from .targets import (  # noqa: F401
    GOALS,
    INTENSITY_METS,
    JOB_FACTORS,
    SEXES,
    Targets,
    compute_targets,
    portion,
)
