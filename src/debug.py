"""
Debug logging to a local SQLite database.

Schema (one row per job run):
  runs            — top-level metadata (url, provider, models, timestamp)
  scraped         — raw page content sent to the parser LLM
  job_details     — structured output from the parser LLM (one column per field)
  resume_output   — structured output from the resume LLM
  cover_letter_output — structured output from the cover letter LLM

Enabled via the --debug flag on the CLI. When disabled, all functions are no-ops.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models import JobDetails, ResumeJSON, CoverLetterJSON

_DB_PATH = Path("debug.db")


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create tables if they don't already exist."""
    conn = _connect()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   TEXT NOT NULL,
            url         TEXT,
            provider    TEXT,
            model       TEXT,
            parser_model TEXT,
            output_folder TEXT
        );

        CREATE TABLE IF NOT EXISTS scraped (
            run_id      INTEGER PRIMARY KEY REFERENCES runs(id),
            raw_content TEXT
        );

        CREATE TABLE IF NOT EXISTS job_details (
            run_id          INTEGER PRIMARY KEY REFERENCES runs(id),
            company         TEXT,
            title           TEXT,
            seniority       TEXT,
            industry        TEXT,
            salary_range    TEXT,
            required_skills TEXT,   -- JSON array
            preferred_skills TEXT,  -- JSON array
            responsibilities TEXT,  -- JSON array
            culture_signals  TEXT   -- JSON array
        );

        CREATE TABLE IF NOT EXISTS resume_output (
            run_id                  INTEGER PRIMARY KEY REFERENCES runs(id),
            summary                 TEXT,
            projects_section_heading TEXT,
            priority                INTEGER,
            priority_reasoning      TEXT,
            skill_categories        TEXT,  -- JSON array
            experience              TEXT,  -- JSON array
            projects                TEXT,  -- JSON array
            certifications          TEXT   -- JSON array
        );

        CREATE TABLE IF NOT EXISTS cover_letter_output (
            run_id          INTEGER PRIMARY KEY REFERENCES runs(id),
            subject_line    TEXT,
            opening         TEXT,
            highlights_intro TEXT,
            closing         TEXT,
            body_paragraphs TEXT,  -- JSON array
            highlights      TEXT   -- JSON array
        );
    """)
    conn.commit()
    conn.close()


def log_run(url: str, provider: str, model: str, parser_model: str) -> int:
    """Insert a new run row and return its id."""
    conn = _connect()
    cur = conn.execute(
        "INSERT INTO runs (timestamp, url, provider, model, parser_model) VALUES (?, ?, ?, ?, ?)",
        (datetime.now().isoformat(timespec="seconds"), url, provider, model, parser_model),
    )
    run_id = cur.lastrowid
    conn.commit()
    conn.close()
    return run_id


def log_output_folder(run_id: int, folder: str) -> None:
    conn = _connect()
    conn.execute("UPDATE runs SET output_folder = ? WHERE id = ?", (folder, run_id))
    conn.commit()
    conn.close()


def log_scraped(run_id: int, raw_content: str) -> None:
    conn = _connect()
    conn.execute(
        "INSERT OR REPLACE INTO scraped (run_id, raw_content) VALUES (?, ?)",
        (run_id, raw_content),
    )
    conn.commit()
    conn.close()


def log_job_details(run_id: int, details: "JobDetails") -> None:
    conn = _connect()
    conn.execute(
        """INSERT OR REPLACE INTO job_details
           (run_id, company, title, seniority, industry, salary_range,
            required_skills, preferred_skills, responsibilities, culture_signals)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            details.company,
            details.title,
            details.seniority,
            details.industry,
            details.salary_range,
            json.dumps(details.required_skills),
            json.dumps(details.preferred_skills),
            json.dumps(details.responsibilities),
            json.dumps(details.culture_signals),
        ),
    )
    conn.commit()
    conn.close()


def log_resume(run_id: int, resume_json: "ResumeJSON") -> None:
    conn = _connect()
    conn.execute(
        """INSERT OR REPLACE INTO resume_output
           (run_id, summary, projects_section_heading, priority, priority_reasoning,
            skill_categories, experience, projects, certifications)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            resume_json.summary,
            resume_json.projects_section_heading,
            resume_json.priority,
            resume_json.priority_reasoning,
            json.dumps([c.model_dump() for c in resume_json.skill_categories]),
            json.dumps([e.model_dump() for e in resume_json.experience]),
            json.dumps([p.model_dump() for p in resume_json.projects]),
            json.dumps(resume_json.certifications),
        ),
    )
    conn.commit()
    conn.close()


def log_cover_letter(run_id: int, cover_json: "CoverLetterJSON") -> None:
    conn = _connect()
    conn.execute(
        """INSERT OR REPLACE INTO cover_letter_output
           (run_id, subject_line, opening, highlights_intro, closing,
            body_paragraphs, highlights)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            run_id,
            cover_json.subject_line,
            cover_json.opening,
            cover_json.highlights_intro,
            cover_json.closing,
            json.dumps(cover_json.body_paragraphs),
            json.dumps(cover_json.highlights),
        ),
    )
    conn.commit()
    conn.close()
