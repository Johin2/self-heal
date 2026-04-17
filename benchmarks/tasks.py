"""Benchmark tasks for self-heal.

Each task is a real (small) Python function with a plausible bug, plus
a set of tests that catch the bug. `self-heal` is measured by how many
tasks it can repair until every test passes.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass


@dataclass
class Task:
    name: str
    description: str
    buggy_source: str         # the buggy function source (complete def)
    function_name: str        # the name of the function defined in the source
    tests: list[Callable]     # each takes the function, raises on failure


# --- individual tasks -------------------------------------------------------


_extract_price_buggy = """
def extract_price(text):
    # Only handles '$X.YY' with no commas, no other currencies.
    return float(text.replace("$", ""))
"""


def _ep_dollars(fn):
    assert fn("$12.99") == 12.99


def _ep_comma(fn):
    assert fn("$1,299") == 1299.0


def _ep_rupee(fn):
    assert fn("₹500") == 500.0


_is_palindrome_buggy = """
def is_palindrome(s):
    # Naive: case-sensitive, doesn't strip punctuation.
    return s == s[::-1]
"""


def _pal_simple(fn):
    assert fn("racecar") is True


def _pal_case(fn):
    assert fn("RaceCar") is True


def _pal_punct(fn):
    assert fn("A man, a plan, a canal: Panama") is True


def _pal_neg(fn):
    assert fn("hello") is False


_count_vowels_buggy = """
def count_vowels(s):
    # Naive: only counts lowercase a,e,i,o,u (misses y and case).
    return sum(1 for c in s if c in "aeiou")
"""


def _cv_lower(fn):
    assert fn("hello") == 2


def _cv_upper(fn):
    assert fn("HELLO") == 2


def _cv_y(fn):
    assert fn("rhythm") == 1


_flatten_buggy = """
def flatten(items):
    # Naive: only flattens one level; fails on deeper nesting.
    out = []
    for x in items:
        if isinstance(x, list):
            out.extend(x)
        else:
            out.append(x)
    return out
"""


def _fl_flat(fn):
    assert fn([1, 2, 3]) == [1, 2, 3]


def _fl_one_level(fn):
    assert fn([1, [2, 3], 4]) == [1, 2, 3, 4]


def _fl_deep(fn):
    assert fn([1, [2, [3, [4]]], 5]) == [1, 2, 3, 4, 5]


_remove_dups_buggy = """
def dedupe(items):
    # Naive: loses order.
    return list(set(items))
"""


def _dd_ints(fn):
    assert fn([1, 2, 2, 3, 1]) == [1, 2, 3]


def _dd_strings(fn):
    assert fn(["b", "a", "b", "c", "a"]) == ["b", "a", "c"]


_reverse_words_buggy = """
def reverse_words(s):
    # Naive: collapses multiple spaces to one.
    return " ".join(s.split()[::-1])
"""


def _rw_normal(fn):
    assert fn("hello world") == "world hello"


def _rw_multispace(fn):
    assert fn("hello  world") == "world  hello"


_roman_to_int_buggy = """
def roman_to_int(s):
    # Naive: doesn't handle subtractive notation (IV, IX, etc.).
    vals = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    return sum(vals[c] for c in s)
"""


def _rm_simple(fn):
    assert fn("III") == 3


def _rm_subtractive(fn):
    assert fn("IV") == 4


def _rm_complex(fn):
    assert fn("MCMXCIV") == 1994


_camel_to_snake_buggy = """
def camel_to_snake(s):
    # Naive: doesn't handle consecutive uppercase letters (HTTPResponse).
    import re
    return re.sub(r'([A-Z])', r'_\\1', s).lower().lstrip('_')
"""


def _cs_simple(fn):
    assert fn("camelCase") == "camel_case"


def _cs_acronym(fn):
    assert fn("HTTPResponse") == "http_response"


def _cs_already_snake(fn):
    assert fn("already_snake") == "already_snake"


_fizzbuzz_buggy = """
def fizzbuzz(n):
    # Naive: returns "Fizz" for 15 instead of "FizzBuzz" (wrong order).
    if n % 3 == 0:
        return "Fizz"
    if n % 5 == 0:
        return "Buzz"
    if n % 15 == 0:
        return "FizzBuzz"
    return str(n)
"""


def _fb_normal(fn):
    assert fn(2) == "2"


def _fb_fizz(fn):
    assert fn(3) == "Fizz"


def _fb_buzz(fn):
    assert fn(5) == "Buzz"


def _fb_fizzbuzz(fn):
    assert fn(15) == "FizzBuzz"


_sum_digits_buggy = """
def sum_digits(n):
    # Naive: breaks on negative numbers.
    return sum(int(c) for c in str(n))
"""


def _sd_positive(fn):
    assert fn(123) == 6


def _sd_negative(fn):
    assert fn(-45) == 9


def _sd_zero(fn):
    assert fn(0) == 0


_gcd_buggy = """
def gcd(a, b):
    # Naive: infinite loop on negative inputs; doesn't handle 0.
    while b != 0:
        a, b = b, a % b
    return a
"""


def _gcd_simple(fn):
    assert fn(12, 8) == 4


def _gcd_negative(fn):
    assert fn(-12, 8) == 4


def _gcd_zero(fn):
    assert fn(7, 0) == 7


_parse_version_buggy = """
def parse_version(s):
    # Naive: returns strings, fails on pre-release tags like '1.2.3-beta'.
    return s.split('.')
"""


def _pv_simple(fn):
    assert fn("1.2.3") == (1, 2, 3)


def _pv_beta(fn):
    assert fn("1.2.3-beta")[:3] == (1, 2, 3)


_is_prime_buggy = """
def is_prime(n):
    # Naive: considers 1 prime; breaks on negatives.
    if n == 2:
        return True
    for i in range(2, n):
        if n % i == 0:
            return False
    return True
"""


def _ip_basic(fn):
    assert fn(7) is True


def _ip_one(fn):
    assert fn(1) is False


def _ip_negative(fn):
    assert fn(-7) is False


def _ip_large(fn):
    assert fn(97) is True


_group_by_buggy = """
def group_by(items, key):
    # Naive: assumes list input is sorted by key.
    out = {}
    for it in items:
        k = key(it)
        out.setdefault(k, []).append(it)
    return out
"""


def _gb_unsorted(fn):
    result = fn([1, 3, 2, 4, 5], lambda x: x % 2)
    assert sorted(result[0]) == [2, 4]
    assert sorted(result[1]) == [1, 3, 5]


def _gb_empty(fn):
    assert fn([], lambda x: x) == {}


_levenshtein_buggy = """
def levenshtein(a, b):
    # Naive: only counts length difference.
    return abs(len(a) - len(b))
"""


def _lv_equal(fn):
    assert fn("kitten", "kitten") == 0


def _lv_classic(fn):
    assert fn("kitten", "sitting") == 3


def _lv_empty(fn):
    assert fn("", "abc") == 3


_format_duration_buggy = """
def format_duration(seconds):
    # Naive: only handles seconds < 60.
    return f"{seconds}s"
"""


def _fd_short(fn):
    assert fn(45) == "45s"


def _fd_minute(fn):
    assert fn(90) == "1m 30s"


def _fd_hour(fn):
    assert fn(3725) == "1h 2m 5s"


_chunks_buggy = """
def chunks(items, n):
    # Naive: off-by-one — returns n-1 items per chunk.
    out = []
    for i in range(0, len(items), n - 1):
        out.append(items[i:i + n - 1])
    return out
"""


def _ck_even(fn):
    assert fn([1, 2, 3, 4], 2) == [[1, 2], [3, 4]]


def _ck_uneven(fn):
    assert fn([1, 2, 3, 4, 5], 2) == [[1, 2], [3, 4], [5]]


def _ck_single(fn):
    assert fn([1, 2, 3], 3) == [[1, 2, 3]]


_anagram_buggy = """
def is_anagram(a, b):
    # Naive: case-sensitive, doesn't ignore spaces.
    return sorted(a) == sorted(b)
"""


def _an_basic(fn):
    assert fn("listen", "silent") is True


def _an_case(fn):
    assert fn("Listen", "Silent") is True


def _an_spaces(fn):
    assert fn("anagram", "nag a ram") is True


_normalize_whitespace_buggy = """
def normalize_whitespace(s):
    # Naive: only collapses spaces, not tabs/newlines.
    while '  ' in s:
        s = s.replace('  ', ' ')
    return s.strip()
"""


def _nw_spaces(fn):
    assert fn("a   b   c") == "a b c"


def _nw_tabs(fn):
    assert fn("a\t\tb\nc") == "a b c"


# --- task list --------------------------------------------------------------


TASKS: list[Task] = [
    Task(
        name="extract_price",
        description="Parse price from multi-currency strings",
        buggy_source=_extract_price_buggy,
        function_name="extract_price",
        tests=[_ep_dollars, _ep_comma, _ep_rupee],
    ),
    Task(
        name="is_palindrome",
        description="Palindrome check (case-insensitive, ignoring punctuation)",
        buggy_source=_is_palindrome_buggy,
        function_name="is_palindrome",
        tests=[_pal_simple, _pal_case, _pal_punct, _pal_neg],
    ),
    Task(
        name="count_vowels",
        description="Count vowels including 'y' and uppercase",
        buggy_source=_count_vowels_buggy,
        function_name="count_vowels",
        tests=[_cv_lower, _cv_upper, _cv_y],
    ),
    Task(
        name="flatten",
        description="Deep-flatten a nested list",
        buggy_source=_flatten_buggy,
        function_name="flatten",
        tests=[_fl_flat, _fl_one_level, _fl_deep],
    ),
    Task(
        name="dedupe",
        description="Remove duplicates while preserving order",
        buggy_source=_remove_dups_buggy,
        function_name="dedupe",
        tests=[_dd_ints, _dd_strings],
    ),
    Task(
        name="reverse_words",
        description="Reverse word order, preserving internal spaces",
        buggy_source=_reverse_words_buggy,
        function_name="reverse_words",
        tests=[_rw_normal, _rw_multispace],
    ),
    Task(
        name="roman_to_int",
        description="Roman numeral to integer (with subtractive notation)",
        buggy_source=_roman_to_int_buggy,
        function_name="roman_to_int",
        tests=[_rm_simple, _rm_subtractive, _rm_complex],
    ),
    Task(
        name="camel_to_snake",
        description="camelCase / HTTPResponse -> snake_case",
        buggy_source=_camel_to_snake_buggy,
        function_name="camel_to_snake",
        tests=[_cs_simple, _cs_acronym, _cs_already_snake],
    ),
    Task(
        name="fizzbuzz",
        description="FizzBuzz (must handle 15 correctly)",
        buggy_source=_fizzbuzz_buggy,
        function_name="fizzbuzz",
        tests=[_fb_normal, _fb_fizz, _fb_buzz, _fb_fizzbuzz],
    ),
    Task(
        name="sum_digits",
        description="Sum decimal digits of an integer (handle negatives)",
        buggy_source=_sum_digits_buggy,
        function_name="sum_digits",
        tests=[_sd_positive, _sd_negative, _sd_zero],
    ),
    Task(
        name="gcd",
        description="Greatest common divisor (handle negatives and zero)",
        buggy_source=_gcd_buggy,
        function_name="gcd",
        tests=[_gcd_simple, _gcd_negative, _gcd_zero],
    ),
    Task(
        name="parse_version",
        description="Parse SemVer string to (major, minor, patch) tuple",
        buggy_source=_parse_version_buggy,
        function_name="parse_version",
        tests=[_pv_simple, _pv_beta],
    ),
    Task(
        name="is_prime",
        description="Primality test (handle 1, 2, negatives)",
        buggy_source=_is_prime_buggy,
        function_name="is_prime",
        tests=[_ip_basic, _ip_one, _ip_negative, _ip_large],
    ),
    Task(
        name="group_by",
        description="Group items by key function (unsorted input)",
        buggy_source=_group_by_buggy,
        function_name="group_by",
        tests=[_gb_unsorted, _gb_empty],
    ),
    Task(
        name="levenshtein",
        description="Levenshtein edit distance",
        buggy_source=_levenshtein_buggy,
        function_name="levenshtein",
        tests=[_lv_equal, _lv_classic, _lv_empty],
    ),
    Task(
        name="format_duration",
        description="Format seconds as '1h 2m 5s'",
        buggy_source=_format_duration_buggy,
        function_name="format_duration",
        tests=[_fd_short, _fd_minute, _fd_hour],
    ),
    Task(
        name="chunks",
        description="Split a list into chunks of size n (off-by-one)",
        buggy_source=_chunks_buggy,
        function_name="chunks",
        tests=[_ck_even, _ck_uneven, _ck_single],
    ),
    Task(
        name="is_anagram",
        description="Anagram check (case-insensitive, ignore spaces)",
        buggy_source=_anagram_buggy,
        function_name="is_anagram",
        tests=[_an_basic, _an_case, _an_spaces],
    ),
    Task(
        name="normalize_whitespace",
        description="Collapse all whitespace (incl. tabs/newlines) to single spaces",
        buggy_source=_normalize_whitespace_buggy,
        function_name="normalize_whitespace",
        tests=[_nw_spaces, _nw_tabs],
    ),
]
