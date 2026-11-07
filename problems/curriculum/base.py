"""
Building blocks for the BashaByte beginner curriculum.

Every problem is a ``Spec``: the statement, hints, an editorial approach and a
reference Python solution. Expected outputs are never typed by hand. They are
produced by running the reference solution on each input, so the statement,
samples and hidden tests can never disagree with each other.
"""

import contextlib
import html
import io
import random
import sys
from dataclasses import dataclass, field
from typing import Callable, List, Optional, Tuple

# Hidden + sample test count per problem cycles through 15..20.
TOTAL_PATTERN = [18, 16, 20, 17, 15, 19]


@dataclass
class Spec:
    slug: str
    title: str
    difficulty: str            # easy | medium
    tags: List[str]
    story: str
    input_format: str
    output_format: str
    constraints: List[str]
    hints: List[str]
    approach: str
    time: str
    space: str
    solution: str
    samples: List[Tuple[str, str]]          # (input, explanation)
    edge: List[str] = field(default_factory=list)
    gen: Optional[Callable[[random.Random], str]] = None
    total: Optional[int] = None

    # ── Rendering ────────────────────────────────────────────
    def description(self) -> str:
        parts = [
            self.story.strip(),
            "Input Format\n" + self.input_format.strip(),
            "Output Format\n" + self.output_format.strip(),
            "Constraints\n" + "\n".join(f"• {c}" for c in self.constraints),
        ]
        return "\n\n".join(parts)

    def editorial_html(self) -> str:
        paras = "".join(
            f"<p>{html.escape(p.strip())}</p>" for p in self.approach.strip().split("\n\n") if p.strip()
        )
        code = html.escape(self.solution.strip("\n"))
        return (
            "<h3>Approach</h3>" + paras
            + "<h3>Python solution</h3>"
            + f'<pre><code class="language-python">{code}</code></pre>'
            + "<p>Try writing it on your own first, then compare. Any language works the same way: "
              "read the input, apply the logic, print exactly the expected format.</p>"
        )


def run_solution(spec: Spec, stdin: str) -> str:
    """Run the reference solution in-process and capture stdout."""
    out = io.StringIO()
    old_stdin = sys.stdin
    sys.stdin = io.StringIO(stdin if stdin.endswith("\n") else stdin + "\n")
    try:
        with contextlib.redirect_stdout(out):
            exec(compile(spec.solution, f"<{spec.slug}>", "exec"), {"__name__": "__main__"})
    finally:
        sys.stdin = old_stdin
    text = out.getvalue()
    lines = text.rstrip("\n").split("\n")
    for line in lines:
        if line != line.rstrip():
            raise ValueError(f"{spec.slug}: trailing whitespace in output for input {stdin!r}")
    result = "\n".join(lines)
    if not result.strip():
        raise ValueError(f"{spec.slug}: empty output for input {stdin!r}")
    return result


def build_cases(spec: Spec, index: int) -> List[dict]:
    """Samples first (3-5), then edge cases, then seeded random cases up to the total."""
    if not 3 <= len(spec.samples) <= 5:
        raise ValueError(f"{spec.slug}: needs 3-5 samples, has {len(spec.samples)}")
    total = spec.total or TOTAL_PATTERN[index % len(TOTAL_PATTERN)]
    rng = random.Random(f"bashabyte::{spec.slug}")

    inputs, seen = [], set()

    def add(raw, explanation=None, sample=False):
        raw = raw.strip("\n")
        if raw in seen:
            return False
        seen.add(raw)
        inputs.append((raw, explanation, sample))
        return True

    for raw, explanation in spec.samples:
        if not add(raw, explanation, True):
            raise ValueError(f"{spec.slug}: duplicate sample {raw!r}")
    for raw in spec.edge:
        if len(inputs) >= total:
            break
        add(raw)
    attempts = 0
    while len(inputs) < total and spec.gen and attempts < 2000:
        attempts += 1
        add(spec.gen(rng))
    if not 15 <= len(inputs) <= 20:
        raise ValueError(f"{spec.slug}: produced {len(inputs)} cases, need 15-20")

    return [
        {
            "order_num": i,
            "input_data": raw,
            "expected_output": run_solution(spec, raw),
            "is_sample": sample,
            "explanation": explanation,
        }
        for i, (raw, explanation, sample) in enumerate(inputs, start=1)
    ]


# ── Small generator helpers ──────────────────────────────────

def line(*values) -> str:
    return " ".join(str(v) for v in values)


def array_input(values, first_line=None) -> str:
    head = str(len(values)) if first_line is None else str(first_line)
    return f"{head}\n{line(*values)}"


def rand_list(rng, n_lo, n_hi, v_lo, v_hi):
    return [rng.randint(v_lo, v_hi) for _ in range(rng.randint(n_lo, n_hi))]


NAMES = [
    "Aarav", "Diya", "Rohan", "Ananya", "Kabir", "Meera", "Arjun", "Isha", "Vikram", "Sneha",
    "Karthik", "Pooja", "Rahul", "Lakshmi", "Imran", "Fatima", "Harpreet", "Joseph", "Nikhil", "Divya",
    "Suresh", "Kavya", "Manoj", "Anjali", "Farhan", "Neha", "Siddharth", "Tanvi", "Gopal", "Ritu",
]

WORDS = [
    "chai", "samosa", "cricket", "monsoon", "rangoli", "diwali", "masala", "dosa", "idli", "biryani",
    "train", "station", "school", "teacher", "student", "market", "mango", "banana", "kite", "festival",
    "temple", "river", "village", "city", "bus", "auto", "ticket", "coder", "python", "laptop",
    "level", "radar", "madam", "racecar", "noon", "refer", "civic", "rotor", "kayak", "stats",
]
