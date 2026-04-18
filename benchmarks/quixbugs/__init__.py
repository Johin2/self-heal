"""QuixBugs benchmark integration for self-heal.

QuixBugs (https://github.com/jkoppel/QuixBugs, MIT) is a corpus of 40
one-line-bug Python programs with reference implementations and JSON
test cases. This loader clones QuixBugs into a local cache dir on first
use and adapts each program into our `Task` shape.
"""

from benchmarks.quixbugs.loader import load_quixbugs_tasks

__all__ = ["load_quixbugs_tasks"]
