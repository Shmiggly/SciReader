"""Natural wording for spoken equations (rule-based and verified AI readings alike).

The rule-based reading (Speech Rule Engine, ClearSpeak) and the checked AI narration both say every structural word:
"U sub c", "open paren", "x to the d-th power". That is what makes them exact, and the verification gate checks the
AI narration in that explicit form. A scientist reading aloud says less, so the default "natural" wording is a
deterministic rewrite of the same text (the user's listening check, 2026-10-21):

- "sub" and "subscript" are not said ("f high of x", "V j m"); a one-symbol argument loses its parentheses
  ("f of x"); "open paren(thesis)" is just "parenthesis";
- "x to the d-th power" is "x to the d power"; a comma before a membership condition is "where";
- "err" is "error";
- kinetics: [A] is "the concentration of A", and d[A]/dt is "the derivative of the concentration of A with respect
  to time";
- for the rule-based reading, a product after a fraction is said with "times" (the LaTeX gets an explicit \\cdot).

"Precise" wording (a reading mode) keeps the explicit text, which is what SciSpeech-Bench scores.
"""

from __future__ import annotations

import re

_SINGLE = r"(?:capital )?(?:[A-Za-z]|\d+|alpha|beta|gamma|delta|epsilon|zeta|eta|theta|iota|kappa|lambda|mu|nu|xi|pi|rho|sigma|tau|upsilon|phi|chi|psi|omega)"
_KINETICS = re.compile(r"\\frac\s*\{\s*d\s*(?:\\left\s*)?\[")
_SPECIES = r"[A-Z](?:[A-Za-z]?\d*'?)"


def natural(spoken: str, latex: str = "") -> str:
    """The natural wording of an explicit equation reading (SRE or a verified AI narration)."""
    s = f" {spoken.strip()} "
    if _KINETICS.search(latex or ""):
        s = _kinetics_words(s)
    # Parentheses around one symbol are not said: "of open parenthesis x close parenthesis" is "of x".
    s = re.sub(rf"\bopen paren(?:thesis)? ({_SINGLE}) close paren(?:thesis)?\b", r"\g<1>", s)
    s = re.sub(r"\bopen paren(?:thesis)?\b", "parenthesis", s)
    s = re.sub(r"\bclose paren\b", "close parenthesis", s)
    s = _drop_unmatched_closers(s)
    s = _pause_before_terms(s)
    s = re.sub(r"\bvertical bar (?:sub|subscript)\b", "evaluated at", s)
    s = re.sub(r"\bend (?:sub|subscript)\b,?\s*", "", s)
    s = re.sub(r"(?<!\bthe )\b(?:sub|subscript)\s+(?=\S)", "", s)  # "the subscript on y" is a noun: kept
    s = re.sub(r"\bto the ([a-zA-Z])-th power\b", r"to the \g<1> power", s)
    s = re.sub(r"\bthe ([a-zA-Z])-th power of\b", r"the \g<1> power of", s)
    s = re.sub(r"\bcomma ((?:capital )?\w+) is a member of\b", r"where \g<1> is a member of", s)
    s = re.sub(r"\berr\b", "error", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip()


def _pause_before_terms(s: str) -> str:
    """A short pause (comma) before "plus" or "minus" between terms (user: "take a pause before saying + or -"), not
    inside a subscript or an exponent ("x sub n plus 1", "e to the minus x"), where it would split the index."""
    out, last = [], 0
    for m in re.finditer(r"(?<=\w) (plus|minus)\b", s):
        if set(s[:m.start()].split()[-2:]) & {"sub", "subscript", "superscript", "the", "to", "or"}:
            continue
        out += [s[last:m.start()], ","]
        last = m.start()
    return "".join(out) + s[last:]


def _drop_unmatched_closers(s: str) -> str:
    """Narrators sometimes open a group with "of" and still close it ("of x … close parenthesis"): without the
    opener the closer means nothing, so the last unmatched ones go."""
    extra = len(re.findall(r"\bclose parenthesis\b", s)) - len(re.findall(r"(?<!close )\bparenthesis\b", s))
    for _ in range(max(0, extra)):
        k = s.rfind(" close parenthesis")
        s = s[:k] + s[k + len(" close parenthesis"):]
    return s


def _kinetics_words(s: str) -> str:
    # SRE reads [A] as "of A" after a symbol and "open bracket A close bracket" elsewhere; AI narrations say
    # "square bracket A close square bracket".
    conc = r"(?:open )?(?:square )?bracket (\w+(?: prime)?) close (?:square )?bracket"
    s = re.sub(conc, r"the concentration of \g<1>", s)
    s = re.sub(r"\bd (the concentration of \w+(?: prime)?)(?: all)? over d t\b", r"the derivative of \g<1> with respect to time", s)
    s = re.sub(r"\bd of (\w+) over d of t\b", r"the derivative of the concentration of \g<1> with respect to time", s)
    # A symbol right before a concentration multiplies it: "b I the concentration of A" is "b I times ...".
    s = re.sub(r"(?<=\b[A-Za-z]) (?=the concentration of\b)", " times ", s)
    s = re.sub(r"\b([A-Za-z]) of ([A-Z]) (?=minus|plus|close|equals)", r"\g<1> times the concentration of \g<2> ", s)
    return s


def prepare_for_rules(latex: str) -> str:
    """LaTeX for the rule-based reading in natural wording: an explicit product after a fraction ("… over V j m,
    times cos psi")."""
    out = []
    i = 0
    n = len(latex)
    while i < n:
        j = latex.find("\\frac", i)
        if j < 0:
            out.append(latex[i:])
            break
        k = _skip_group(latex, _skip_group(latex, j + 5))
        if k < 0:
            out.append(latex[i:])
            break
        # Step over the braces that wrap the fraction ("{ \frac{a}{b} } \cos").
        m = k
        while m < n and latex[m] in " }":
            m += 1
        out.append(latex[i:m])
        nxt = latex[m:m + 16]
        if m < n and (nxt[:1].isalpha() or nxt[:1] in "(" or re.match(r"\\(?!right|cdot|times|quad|qquad|,|;|!|\s)[A-Za-z]+", nxt)):
            out.append(" \\cdot ")
        i = m
    return "".join(out)


def _skip_group(s: str, i: int) -> int:
    """Index after the balanced {...} group starting at the first "{" at or after i, or -1."""
    while i < len(s) and s[i] == " ":
        i += 1
    if i >= len(s) or s[i] != "{":
        return -1
    depth = 0
    while i < len(s):
        if s[i] == "\\":
            i += 2
            continue
        depth += {"{": 1, "}": -1}.get(s[i], 0)
        i += 1
        if depth == 0:
            return i
    return -1
