"""Tests for semantic.sql_lex GoogleSQL lexer and escaper."""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pytest  # noqa: E402

from semantic.sql_lex import (  # noqa: E402
    extract_qualified_columns,
    format_googlesql_string_literal,
    has_multiple_statements,
    parse_single_aggregate,
    rewrite_base_table_qualifiers,
    strip_sql_literals_and_comments,
)


def test_format_googlesql_string_literal_basic() -> None:
    assert format_googlesql_string_literal("hello") == "'hello'"
    assert format_googlesql_string_literal("O'Brien") == r"'O\'Brien'"
    assert format_googlesql_string_literal("trailing \\") == r"'trailing \\'"
    assert format_googlesql_string_literal("line1\nline2") == r"'line1\nline2'"
    assert format_googlesql_string_literal("tab\tchar") == r"'tab\tchar'"
    assert format_googlesql_string_literal("cr\rchar") == r"'cr\rchar'"
    assert format_googlesql_string_literal("ctrl\x1b\x7f") == r"'ctrl\x1b\x7f'"


def test_format_googlesql_string_literal_rejections() -> None:
    with pytest.raises(ValueError, match="requires str"):
        format_googlesql_string_literal(123)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="requires str"):
        format_googlesql_string_literal(None)  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="NUL"):
        format_googlesql_string_literal("null\x00byte")


def test_strip_sql_literals_and_comments() -> None:
    sql = (
        "SELECT 'single', \"double\", '''triple single''', \"\"\"triple double\"\"\", "
        "-- line comment\n"
        "# googlesql hash comment\n"
        "/* block comment */ col1 FROM orders"
    )
    stripped = strip_sql_literals_and_comments(sql)
    assert "'single'" not in stripped
    assert '"double"' not in stripped
    assert "'''triple single'''" not in stripped
    assert "line comment" not in stripped
    assert "googlesql hash comment" not in stripped
    assert "block comment" not in stripped
    assert "SELECT" in stripped
    assert "col1" in stripped
    assert "FROM orders" in stripped


def test_has_multiple_statements() -> None:
    assert not has_multiple_statements("SELECT 1")
    assert not has_multiple_statements("SELECT 1;")
    assert not has_multiple_statements("SELECT 1;   ")
    assert not has_multiple_statements("SELECT 1; -- trailing comment\n")
    assert not has_multiple_statements("SELECT 1; /* trailing block */")

    assert has_multiple_statements("SELECT 1;;")
    assert has_multiple_statements("SELECT 1; SELECT 2")
    assert has_multiple_statements("SELECT 1; SELECT 2;")
    assert has_multiple_statements("SELECT 1; -- comment\n SELECT 2;")


def test_extract_qualified_columns() -> None:
    sql = (
        "SELECT orders.order_id, `users`.`country`, order_items.sale_price, "
        "SAFE.DIVIDE(order_items.sale_price, 2), "
        "COUNT(orders.order_id) "
        "FROM orders"
    )
    cols = extract_qualified_columns(sql)
    assert ("orders", "order_id") in cols
    assert ("users", "country") in cols
    assert ("order_items", "sale_price") in cols
    # Function calls must NOT be captured as qualified columns
    assert ("SAFE", "DIVIDE") not in cols


def test_rewrite_base_table_qualifiers() -> None:
    sql = (
        "orders.status = 'Complete' AND users.country = 'USA' "
        "AND SAFE.DIVIDE(orders.order_id, 2) > 0"
    )
    rewritten, base_cols, ext_tables = rewrite_base_table_qualifiers(sql, "orders")

    assert "status = 'Complete'" in rewritten
    assert "users.country = 'USA'" in rewritten
    assert "orders.status" not in rewritten
    assert base_cols == ("status", "order_id")
    assert ext_tables == ("users",)


def test_parse_single_aggregate() -> None:
    # Valid standard aggregates
    assert parse_single_aggregate("SUM(order_items.sale_price)") == (
        "SUM",
        False,
        "order_items.sale_price",
    )
    assert parse_single_aggregate("COUNT(DISTINCT order_items.order_id)") == (
        "COUNT",
        True,
        "order_items.order_id",
    )
    assert parse_single_aggregate("AVG(col)") == ("AVG", False, "col")
    assert parse_single_aggregate("MIN(t.val)") == ("MIN", False, "t.val")
    assert parse_single_aggregate("MAX(DISTINCT t.val)") == ("MAX", True, "t.val")

    # CASE statements inside aggregate
    assert parse_single_aggregate(
        "COUNT(DISTINCT CASE WHEN orders.status = 'Complete' THEN orders.user_id END)"
    ) == (
        "COUNT",
        True,
        "CASE WHEN orders.status = 'Complete' THEN orders.user_id END",
    )

    # Rejection of compound expressions (L2 and L4)
    assert parse_single_aggregate("SUM(t.a) - SUM(t.b)") is None
    assert parse_single_aggregate("COUNT(DISTINCT a) + SUM(b)") is None
    assert parse_single_aggregate("COUNT(DISTINCT a) / COUNT(b)") is None
    assert parse_single_aggregate("SUM(a) + 1") is None

    # Rejection of non-aggregates or malformed syntax
    assert parse_single_aggregate("order_items.sale_price") is None
    assert parse_single_aggregate("SUM(a") is None
    assert parse_single_aggregate("SUM()") is None
    assert parse_single_aggregate("") is None
