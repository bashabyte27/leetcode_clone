"""
BashaByte beginner DSA curriculum: 100 problems that step from first print
statement to LeetCode-easy level.

    from problems.curriculum import CURRICULUM, build_cases
"""

from .base import Spec, build_cases, run_solution
from . import stage1_basics, stage2_loops, stage3_arrays, stage4_strings, stage5_mixed

CURRICULUM = (
    stage1_basics.SPECS
    + stage2_loops.SPECS
    + stage3_arrays.SPECS
    + stage4_strings.SPECS
    + stage5_mixed.SPECS
)

# Stage boundaries (1-based position inside the curriculum) for documentation / UI.
STAGES = [
    (1, 12, "Input, Output and Arithmetic"),
    (13, 24, "Conditions"),
    (25, 40, "Loops and Number Logic"),
    (41, 48, "Patterns"),
    (49, 70, "Arrays"),
    (71, 88, "Strings"),
    (89, 100, "Hashing, Matrices and Capstone"),
]

__all__ = ["CURRICULUM", "STAGES", "Spec", "build_cases", "run_solution"]
