#!/usr/bin/env python3
"""Minimal fixed-boundary sqlite runner for Codex++ session maintenance."""

from __future__ import annotations

import argparse
import base64
import contextlib
import io
import os
import sqlite3
import sys


EXPECTED_DATABASE = os.path.normcase(
    os.path.realpath(os.path.abspath(r"@@CODEXPP_HOME:win@@\state_5.sqlite"))
)


def emit_rows(cursor: sqlite3.Cursor) -> None:
    for row in cursor.fetchall():
        print("|".join("" if value is None else str(value) for value in row))


def iter_statements(sql: str):
    buffer: list[str] = []
    for character in sql:
        buffer.append(character)
        if character == ";" and sqlite3.complete_statement("".join(buffer)):
            statement = "".join(buffer).strip()
            if statement:
                yield statement
            buffer.clear()
    remainder = "".join(buffer).strip()
    if remainder:
        yield remainder


def execute_sql(connection: sqlite3.Connection, sql: str) -> None:
    for statement in iter_statements(sql):
        cursor = connection.execute(statement)
        if cursor.description is not None:
            emit_rows(cursor)


def run_self_test() -> int:
    connection = sqlite3.connect(":memory:")
    try:
        captured = io.StringIO()
        with contextlib.redirect_stdout(captured):
            execute_sql(
                connection,
                "CREATE TABLE probe(id INTEGER PRIMARY KEY, value TEXT);"
                "CREATE TRIGGER probe_upper AFTER INSERT ON probe "
                "BEGIN UPDATE probe SET value = upper(NEW.value) WHERE id = NEW.id; END;"
                "INSERT INTO probe(value) VALUES ('alpha');"
                "SELECT value FROM probe WHERE id = 1;"
                "SELECT lower(value) FROM probe WHERE id = 1;",
            )
            connection.commit()
            execute_sql(
                connection,
                "BEGIN IMMEDIATE;"
                "INSERT INTO probe(value) VALUES ('beta');"
                "SELECT value FROM probe WHERE id = 2;"
                "ROLLBACK;"
                "SELECT count(*) FROM probe;",
            )
        output = captured.getvalue().splitlines()
        if output != ["ALPHA", "alpha", "BETA", "1"]:
            raise RuntimeError(f"unexpected sqlite self-test output: {output!r}")
        rows = connection.execute("SELECT id, value FROM probe ORDER BY id;").fetchall()
        if rows != [(1, "ALPHA")]:
            raise RuntimeError(f"unexpected sqlite self-test rows after rollback: {rows!r}")
    finally:
        connection.close()
    print("CODEXPP_SQLITE_HELPER_SELF_TEST_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--self-test", action="store_true")
    parser.add_argument("--database")
    parser.add_argument("--timeout-ms", type=int, default=2000)
    parser.add_argument("--sql-base64")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    if not args.database or not args.sql_base64:
        parser.error("--database and --sql-base64 are required outside --self-test")
    if not 1 <= args.timeout_ms <= 60000:
        parser.error("--timeout-ms must be between 1 and 60000")
    database = os.path.normcase(os.path.realpath(os.path.abspath(args.database)))
    if database != EXPECTED_DATABASE:
        raise RuntimeError(f"refusing sqlite database outside fixed Codex++ state DB: {database}")
    sql = base64.b64decode(args.sql_base64, validate=True).decode("utf-8")
    connection = sqlite3.connect(database, timeout=args.timeout_ms / 1000.0)
    try:
        connection.execute(f"PRAGMA busy_timeout = {args.timeout_ms:d};")
        execute_sql(connection, sql)
        connection.commit()
    finally:
        connection.close()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"CODEXPP_SQLITE_HELPER_FAIL: {exc}", file=sys.stderr)
        raise SystemExit(1)
