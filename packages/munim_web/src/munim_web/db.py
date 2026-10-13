"""SQLite: connection, migrations and the repository functions (plain SQL, no ORM).

Routes never write SQL; services call these functions. Every handler is async and runs on the
event loop thread, so one connection is shared. PRAGMAs: foreign keys, WAL, secure_delete.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from importlib import resources
from pathlib import Path
from typing import Any

import yaml
from ulid import ULID

__all__ = ["Database", "new_id", "now"]


def new_id() -> str:
    return str(ULID())


def now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


@dataclass
class Database:
    path: Path
    conn: sqlite3.Connection

    @classmethod
    def open(cls, path: Path) -> Database:
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, check_same_thread=False, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA secure_delete = ON")
        db = cls(path, conn)
        db.migrate()
        return db

    def close(self) -> None:
        self.conn.close()

    # ------------------------------------------------------------ migrations
    def migrate(self) -> list[str]:
        self.conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_migrations (name TEXT PRIMARY KEY, applied_at TEXT NOT NULL)"
        )
        done = {r["name"] for r in self.conn.execute("SELECT name FROM schema_migrations")}
        applied = []
        folder = resources.files("munim_web.migrations")
        for entry in sorted(folder.iterdir(), key=lambda e: e.name):
            if not entry.name.endswith(".sql") or entry.name in done:
                continue
            script = entry.read_text(encoding="utf-8")
            self.conn.executescript(
                "BEGIN;\n"
                + script
                + f"\nINSERT INTO schema_migrations VALUES ('{entry.name}', '{now()}');\nCOMMIT;"
            )
            applied.append(entry.name)
        return applied

    def seed_bank_rates(self, rules_dir: Path) -> None:
        """Load rules/bank_rate.yaml into an empty table (the person confirms rows later)."""
        if self.conn.execute("SELECT 1 FROM bank_rates LIMIT 1").fetchone():
            return
        rows = yaml.safe_load((rules_dir / "bank_rate.yaml").read_text(encoding="utf-8")) or []
        for row in rows:
            self.conn.execute(
                "INSERT INTO bank_rates (effective_from, percent, source, confirmed) VALUES (?, ?, ?, ?)",
                (
                    str(row["effective_from"]),
                    str(row["percent"]),
                    row["source"],
                    int(bool(row["confirmed"])),
                ),
            )

    def fail_stuck_reads(self) -> int:
        """Papers left reading by a stopped server cannot finish; mark them failed."""
        cur = self.conn.execute(
            "UPDATE papers SET status = 'failed', error = 'error.interrupted' WHERE status IN ('reading', 'repairing')"
        )
        return cur.rowcount

    # ------------------------------------------------------------ helpers
    def one(self, sql: str, args: Iterable[Any] = ()) -> sqlite3.Row | None:
        row: sqlite3.Row | None = self.conn.execute(sql, tuple(args)).fetchone()
        return row

    def all(self, sql: str, args: Iterable[Any] = ()) -> list[sqlite3.Row]:
        return list(self.conn.execute(sql, tuple(args)).fetchall())

    def run(self, sql: str, args: Iterable[Any] = ()) -> int:
        return self.conn.execute(sql, tuple(args)).rowcount

    def event(self, case_id: str | None, event_kind: str, **detail: str | int | None) -> None:
        """Append to the audit log. Detail carries ids and outcomes, never values."""
        self.run(
            "INSERT INTO events (case_id, at, kind, detail_json) VALUES (?, ?, ?, ?)",
            (case_id, now(), event_kind, json.dumps(detail, sort_keys=True)),
        )

    # ------------------------------------------------------------ cases
    def create_case(self, title: str, supplier: str, buyer: str) -> str:
        case_id = new_id()
        stamp = now()
        self.run(
            "INSERT INTO cases (id, title, supplier_name, buyer_name, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            (case_id, title, supplier, buyer, stamp, stamp),
        )
        self.event(case_id, "case.created")
        return case_id

    def case(self, case_id: str) -> sqlite3.Row | None:
        return self.one("SELECT * FROM cases WHERE id = ?", (case_id,))

    def cases(self) -> list[sqlite3.Row]:
        return self.all("SELECT * FROM cases ORDER BY updated_at DESC")

    def update_case(self, case_id: str, values: Mapping[str, Any]) -> None:
        allowed = {
            "title",
            "supplier_name",
            "buyer_name",
            "supplier_address",
            "buyer_address",
            "udyam_number",
            "udyam_date",
            "enterprise_size",
            "agreement",
            "credit_days",
            "objection_removed_on",
            "acceptance_date",
            "interest_base",
            "as_on_date",
            "notice_days",
        }
        keys = [k for k in values if k in allowed]
        if not keys:
            return
        sets = ", ".join(f"{k} = ?" for k in keys)
        self.run(
            f"UPDATE cases SET {sets}, confirmed_at = NULL, updated_at = ? WHERE id = ?",  # noqa: S608 - keys are allow-listed
            [values[k] for k in keys] + [now(), case_id],
        )

    def touch(self, case_id: str, *, unconfirm: bool = True) -> None:
        if unconfirm:
            self.run(
                "UPDATE cases SET confirmed_at = NULL, updated_at = ? WHERE id = ?",
                (now(), case_id),
            )
        else:
            self.run("UPDATE cases SET updated_at = ? WHERE id = ?", (now(), case_id))

    def confirm(self, case_id: str) -> None:
        self.run(
            "UPDATE cases SET confirmed_at = ?, updated_at = ? WHERE id = ?",
            (now(), now(), case_id),
        )

    def delete_case(self, case_id: str) -> None:
        self.run("DELETE FROM events WHERE case_id = ?", (case_id,))
        self.run("DELETE FROM cases WHERE id = ?", (case_id,))
        self.conn.execute("VACUUM")
        self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")

    # ------------------------------------------------------------ papers
    def add_paper(
        self, case_id: str, paper_id: str, *, kind: str, original: str, sha256: str, file_type: str
    ) -> None:
        self.run(
            "INSERT INTO papers (id, case_id, kind, original_path, sha256, file_type, status, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, 'added', ?)",
            (paper_id, case_id, kind, original, sha256, file_type, now()),
        )

    def paper(self, paper_id: str) -> sqlite3.Row | None:
        return self.one("SELECT * FROM papers WHERE id = ?", (paper_id,))

    def papers(self, case_id: str) -> list[sqlite3.Row]:
        return self.all(
            "SELECT * FROM papers WHERE case_id = ? ORDER BY CASE kind WHEN 'invoice' THEN 0 WHEN 'challan' THEN 1 ELSE 2 END",
            (case_id,),
        )

    def update_paper(self, paper_id: str, **values: Any) -> None:
        keys = list(values)
        sets = ", ".join(f"{k} = ?" for k in keys)
        self.run(f"UPDATE papers SET {sets} WHERE id = ?", [values[k] for k in keys] + [paper_id])  # noqa: S608 - internal keys only

    def delete_paper(self, paper_id: str) -> None:
        self.run("DELETE FROM papers WHERE id = ?", (paper_id,))

    # ------------------------------------------------------------ claims
    def replace_claims(self, paper_id: str, rows: Iterable[Mapping[str, Any]]) -> None:
        self.conn.execute("BEGIN")
        try:
            self.run("DELETE FROM claims WHERE paper_id = ?", (paper_id,))
            for r in rows:
                box = r.get("box") or (None, None, None, None)
                self.run(
                    "INSERT INTO claims (id, paper_id, field, line_index, value_read, value_current, "
                    "box_y1, box_x1, box_y2, box_x2, source, review_flag) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        new_id(),
                        paper_id,
                        r["field"],
                        r["line_index"],
                        r["value_read"],
                        r["value"],
                        *box,
                        r.get("source", "model"),
                        r.get("flag"),
                    ),
                )
            self.conn.execute("COMMIT")
        except Exception:
            self.conn.execute("ROLLBACK")
            raise

    def claim(self, claim_id: str) -> sqlite3.Row | None:
        return self.one(
            "SELECT claims.*, papers.case_id, papers.kind FROM claims JOIN papers ON papers.id = claims.paper_id WHERE claims.id = ?",
            (claim_id,),
        )

    def claims_for_case(self, case_id: str) -> list[sqlite3.Row]:
        return self.all(
            "SELECT claims.*, papers.kind, papers.case_id FROM claims JOIN papers ON papers.id = claims.paper_id "
            "WHERE papers.case_id = ? ORDER BY papers.kind, claims.line_index, claims.rowid",
            (case_id,),
        )

    def set_claim_value(self, claim_id: str, value: str | None, source: str, **extra: Any) -> None:
        keys = list(extra)
        sets = "".join(f", {k} = ?" for k in keys)
        self.run(
            f"UPDATE claims SET value_current = ?, source = ?, version = version + 1{sets} WHERE id = ?",  # noqa: S608 - internal keys only
            [value, source, *[extra[k] for k in keys], claim_id],
        )

    def update_claim(self, claim_id: str, **values: Any) -> None:
        keys = list(values)
        sets = ", ".join(f"{k} = ?" for k in keys)
        self.run(f"UPDATE claims SET {sets} WHERE id = ?", [values[k] for k in keys] + [claim_id])  # noqa: S608 - internal keys only

    # ------------------------------------------------------------ acceptances, payments, rates
    def add_acceptance(
        self,
        case_id: str,
        rule_id: str,
        fields: list[list[Any]],
        versions: dict[str, int],
        reason: str,
    ) -> None:
        self.run(
            "INSERT INTO acceptances (id, case_id, rule_id, fields_json, versions_json, reason, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                new_id(),
                case_id,
                rule_id,
                json.dumps(fields),
                json.dumps(versions, sort_keys=True),
                reason,
                now(),
            ),
        )

    def acceptances(self, case_id: str) -> list[sqlite3.Row]:
        return self.all(
            "SELECT * FROM acceptances WHERE case_id = ? ORDER BY created_at", (case_id,)
        )

    def add_payment(self, case_id: str, paid_on: str, amount_paise: int) -> None:
        self.run(
            "INSERT INTO payments (id, case_id, paid_on, amount_paise) VALUES (?, ?, ?, ?)",
            (new_id(), case_id, paid_on, amount_paise),
        )

    def payments(self, case_id: str) -> list[sqlite3.Row]:
        return self.all("SELECT * FROM payments WHERE case_id = ? ORDER BY paid_on", (case_id,))

    def delete_payment(self, case_id: str, payment_id: str) -> None:
        self.run("DELETE FROM payments WHERE id = ? AND case_id = ?", (payment_id, case_id))

    def bank_rates(self) -> list[sqlite3.Row]:
        return self.all("SELECT * FROM bank_rates ORDER BY effective_from")

    def upsert_bank_rate(
        self, effective_from: str, percent: str, source: str, confirmed: bool
    ) -> None:
        self.run(
            "INSERT INTO bank_rates (effective_from, percent, source, confirmed) VALUES (?, ?, ?, ?) "
            "ON CONFLICT(effective_from) DO UPDATE SET percent = excluded.percent, source = excluded.source, "
            "confirmed = excluded.confirmed",
            (effective_from, percent, source, int(confirmed)),
        )

    # ------------------------------------------------------------ settings
    def setting(self, key: str) -> str | None:
        row = self.one("SELECT value FROM settings WHERE key = ?", (key,))
        return str(row["value"]) if row else None

    def set_setting(self, key: str, value: str) -> None:
        self.run(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )
