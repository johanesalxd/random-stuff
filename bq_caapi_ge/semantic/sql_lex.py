"""Deterministic GoogleSQL lexer, tokenizer, and literal escaper.

Zero external dependencies (stdlib only).
Handles standard GoogleSQL string literals, raw strings, comments, and identifiers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class TokenType(Enum):
    WHITESPACE = auto()
    COMMENT = auto()
    STRING = auto()
    BACKTICK = auto()
    IDENT = auto()
    NUMBER = auto()
    PUNCT = auto()
    OTHER = auto()


@dataclass(frozen=True)
class Token:
    type: TokenType
    text: str
    start: int
    end: int


def tokenize_googlesql(sql: str) -> list[Token]:
    """Scans GoogleSQL text character-by-character into a list of Tokens."""
    tokens: list[Token] = []
    n = len(sql)
    i = 0

    while i < n:
        ch = sql[i]

        # 1. Whitespace
        if ch.isspace():
            start = i
            while i < n and sql[i].isspace():
                i += 1
            tokens.append(Token(TokenType.WHITESPACE, sql[start:i], start, i))
            continue

        # 2. Line comment: -- or #
        if (ch == "-" and i + 1 < n and sql[i + 1] == "-") or (ch == "#"):
            start = i
            while i < n and sql[i] != "\n":
                i += 1
            if i < n and sql[i] == "\n":
                i += 1
            tokens.append(Token(TokenType.COMMENT, sql[start:i], start, i))
            continue

        # 3. Block comment: /* ... */
        if ch == "/" and i + 1 < n and sql[i + 1] == "*":
            start = i
            i += 2
            while i + 1 < n and not (sql[i] == "*" and sql[i + 1] == "/"):
                i += 1
            if i + 1 < n:
                i += 2  # consume */
            else:
                i = n
            tokens.append(Token(TokenType.COMMENT, sql[start:i], start, i))
            continue

        # 4. String literals: single, double, triple, and raw strings (r'...' / R"...")
        is_raw = False
        quote_start = i
        if ch in ("r", "R") and i + 1 < n and sql[i + 1] in ("'", '"'):
            is_raw = True
            quote_start = i + 1

        if sql[quote_start] in ("'", '"'):
            start = i
            qchar = sql[quote_start]
            is_triple = quote_start + 2 < n and sql[quote_start : quote_start + 3] == qchar * 3
            if is_triple:
                delimiter = qchar * 3
                i = quote_start + 3
                while i < n:
                    if sql[i : i + 3] == delimiter:
                        i += 3
                        break
                    if not is_raw and sql[i] == "\\":
                        i += 2
                    else:
                        i += 1
            else:
                delimiter = qchar
                i = quote_start + 1
                while i < n:
                    if sql[i] == delimiter:
                        i += 1
                        break
                    if not is_raw and sql[i] == "\\":
                        i += 2
                    else:
                        i += 1
            tokens.append(Token(TokenType.STRING, sql[start:i], start, i))
            continue

        # 5. Backtick identifier: `...`
        if ch == "`":
            start = i
            i += 1
            while i < n:
                if sql[i] == "`":
                    i += 1
                    break
                if sql[i] == "\\":
                    i += 2
                else:
                    i += 1
            tokens.append(Token(TokenType.BACKTICK, sql[start:i], start, i))
            continue

        # 6. Unquoted Identifier: [A-Za-z_][A-Za-z0-9_]*
        if ch.isalpha() or ch == "_":
            start = i
            while i < n and (sql[i].isalnum() or sql[i] == "_"):
                i += 1
            tokens.append(Token(TokenType.IDENT, sql[start:i], start, i))
            continue

        # 7. Number: digits with optional decimal point and exponent
        if ch.isdigit():
            start = i
            while i < n and sql[i].isdigit():
                i += 1
            if i < n and sql[i] == "." and (i + 1 == n or sql[i + 1] != "."):
                i += 1
                while i < n and sql[i].isdigit():
                    i += 1
            if i < n and sql[i] in ("e", "E"):
                i += 1
                if i < n and sql[i] in ("+", "-"):
                    i += 1
                while i < n and sql[i].isdigit():
                    i += 1
            tokens.append(Token(TokenType.NUMBER, sql[start:i], start, i))
            continue

        # 8. Punctuation / Operator / Other single chars
        tokens.append(Token(TokenType.PUNCT, ch, i, i + 1))
        i += 1

    return tokens


def strip_sql_literals_and_comments(sql: str) -> str:
    """Replaces string literals and comments with single spaces.

    Preserves identifiers, backticks, numbers, whitespace, and punctuation.
    """
    tokens = tokenize_googlesql(sql)
    chunks: list[str] = []
    for tok in tokens:
        if tok.type in (TokenType.STRING, TokenType.COMMENT):
            chunks.append(" ")
        else:
            chunks.append(tok.text)
    return "".join(chunks)


def has_multiple_statements(sql: str) -> bool:
    """Checks whether the SQL text contains multiple statements.

    Allows zero semicolons OR one trailing ';' followed only by whitespace/comments.
    Returns True if any ';' is followed by another non-whitespace, non-comment token
    (or another ';').
    """
    tokens = tokenize_googlesql(sql)
    non_ignorable = [t for t in tokens if t.type not in (TokenType.WHITESPACE, TokenType.COMMENT)]
    if not non_ignorable:
        return False

    semicolon_indices = [idx for idx, t in enumerate(non_ignorable) if t.text == ";"]
    if not semicolon_indices:
        return False

    # If there is more than 1 semicolon, or the only semicolon is not the last token:
    if len(semicolon_indices) > 1:
        return True
    return semicolon_indices[0] != len(non_ignorable) - 1


def _unquote_ident(tok_text: str) -> str:
    if tok_text.startswith("`") and tok_text.endswith("`") and len(tok_text) >= 2:
        return tok_text[1:-1].replace("\\`", "`").replace("\\\\", "\\")
    return tok_text


def extract_qualified_columns(sql: str) -> tuple[tuple[str, str], ...]:
    """Scans tokens outside literals/comments for `<qualifier>.<col>`.

    Excludes function calls like `SAFE.DIVIDE(...)` where `<col>` is followed by `(`.
    Returns tuples of `(qualifier, col)` in order of appearance.
    """
    tokens = tokenize_googlesql(sql)
    non_ignorable = [t for t in tokens if t.type not in (TokenType.WHITESPACE, TokenType.COMMENT)]
    results: list[tuple[str, str]] = []

    m = len(non_ignorable)
    for idx in range(m - 2):
        t_qual = non_ignorable[idx]
        t_dot = non_ignorable[idx + 1]
        t_col = non_ignorable[idx + 2]

        if t_qual.type in (TokenType.IDENT, TokenType.BACKTICK) and t_dot.text == "." and t_col.type in (TokenType.IDENT, TokenType.BACKTICK):
            # Check if followed by '('
            if idx + 3 < m and non_ignorable[idx + 3].text == "(":
                continue
            qualifier = _unquote_ident(t_qual.text)
            col = _unquote_ident(t_col.text)
            results.append((qualifier, col))

    return tuple(results)


def rewrite_base_table_qualifiers(
    sql: str, base_table: str
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    """Rewrites `<base_table>.<col>` to `<col>` outside string literals/comments.

    Only applies to exact case-sensitive matches of `base_table` not followed by `(`.
    Returns:
        (rewritten_sql, unique_base_columns_in_order, unique_external_table_qualifiers_in_order)
    """
    tokens = tokenize_googlesql(sql)
    # Filter to non-whitespace, non-comment to detect patterns and spans
    non_ignorable = [t for t in tokens if t.type not in (TokenType.WHITESPACE, TokenType.COMMENT)]

    base_cols: list[str] = []
    ext_tables: list[str] = []
    slices_to_remove: list[tuple[int, int]] = []

    m = len(non_ignorable)
    for idx in range(m - 2):
        t_qual = non_ignorable[idx]
        t_dot = non_ignorable[idx + 1]
        t_col = non_ignorable[idx + 2]

        if t_qual.type in (TokenType.IDENT, TokenType.BACKTICK) and t_dot.text == "." and t_col.type in (TokenType.IDENT, TokenType.BACKTICK):
            if idx + 3 < m and non_ignorable[idx + 3].text == "(":
                continue

            qual_name = _unquote_ident(t_qual.text)
            col_name = _unquote_ident(t_col.text)

            if qual_name == base_table:
                if col_name not in base_cols:
                    base_cols.append(col_name)
                # Remove the qualifier and dot: from t_qual.start to t_col.start
                slices_to_remove.append((t_qual.start, t_col.start))
            else:
                if qual_name not in ext_tables:
                    ext_tables.append(qual_name)

    if not slices_to_remove:
        return sql, tuple(base_cols), tuple(ext_tables)

    # Apply removals from right to left
    slices_to_remove.sort(key=lambda x: x[0], reverse=True)
    out = sql
    for start, end in slices_to_remove:
        out = out[:start] + out[end:]

    return out, tuple(base_cols), tuple(ext_tables)


def parse_single_aggregate(sql: str) -> tuple[str, bool, str] | None:
    """Parses a single top-level SQL aggregate function call.

    Verifies that the expression consists of exactly one top-level
    AGG_FUNC( [DISTINCT] inner_expr ) where the matching closing parenthesis
    is the final meaningful token. Rejects compound expressions such as
    `SUM(a) - SUM(b)` or `COUNT(DISTINCT a) + SUM(b)`.

    Returns:
        (agg_func_upper, is_distinct, inner_expr_stripped) or None if invalid.
    """
    raw_tokens = tokenize_googlesql(sql)
    tokens = [t for t in raw_tokens if t.type not in (TokenType.WHITESPACE, TokenType.COMMENT)]
    if len(tokens) < 3:
        return None

    first = tokens[0]
    if first.type != TokenType.IDENT:
        return None
    agg_func = first.text.upper()

    if tokens[1].type != TokenType.PUNCT or tokens[1].text != "(":
        return None

    depth = 0
    closing_idx = -1
    for idx in range(1, len(tokens)):
        t = tokens[idx]
        if t.type == TokenType.PUNCT:
            if t.text == "(":
                depth += 1
            elif t.text == ")":
                depth -= 1
                if depth == 0:
                    closing_idx = idx
                    break

    if depth != 0 or closing_idx == -1:
        return None

    if closing_idx != len(tokens) - 1:
        return None

    inner_tokens = tokens[2:closing_idx]
    if not inner_tokens:
        return None

    is_distinct = False
    if inner_tokens[0].type == TokenType.IDENT and inner_tokens[0].text.upper() == "DISTINCT":
        is_distinct = True
        expr_tokens = inner_tokens[1:]
    else:
        expr_tokens = inner_tokens

    if not expr_tokens:
        return None

    start_pos = expr_tokens[0].start
    end_pos = expr_tokens[-1].end
    inner_expr = sql[start_pos:end_pos].strip()
    return (agg_func, is_distinct, inner_expr)


def format_googlesql_string_literal(value: str) -> str:
    """Escapes and quotes a string value into a standard GoogleSQL literal.

    Raises:
        ValueError: If value is not a string or contains a NUL byte.
    """
    if not isinstance(value, str):
        raise ValueError(f"GoogleSQL string literal requires str, got {type(value).__name__}")
    if "\x00" in value:
        raise ValueError("GoogleSQL string literal cannot contain NUL (0x00) byte")

    escaped_chars: list[str] = []
    for ch in value:
        if ch == "\\":
            escaped_chars.append("\\\\")
        elif ch == "'":
            escaped_chars.append("\\'")
        elif ch == "\n":
            escaped_chars.append("\\n")
        elif ch == "\r":
            escaped_chars.append("\\r")
        elif ch == "\t":
            escaped_chars.append("\\t")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            escaped_chars.append(f"\\x{ord(ch):02x}")
        else:
            escaped_chars.append(ch)

    return f"'{''.join(escaped_chars)}'"
