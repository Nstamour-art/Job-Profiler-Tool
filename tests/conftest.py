import pytest


@pytest.fixture
def sample_config():
    return {
        "llm": {
            "temperature": 0.3,
            "max_retries": 1,
            "model": "llama3.2:latest",
            "parser_model": "llama3.2:latest",
            "anthropic": {
                "model": "claude-haiku-4-5-20251001",
                "parser_model": "claude-haiku-4-5-20251001",
                "fallback_models": [],
                "parser_fallback_models": [],
            },
        },
        "paths": {
            "resume_yaml": "resume.yaml",
            "output_dir": "output",
            "credentials": "credentials/google_service_account.json",
        },
        "google_sheets": {
            "spreadsheet_id": "test-sheet-id",
            "worksheet_name": "Sheet1",
            "columns": {
                "job_title": "Title",
                "company": "Company",
                "url": "URL",
                "status": "Status",
                "date_found": "Date Found",
                "details": "Details",
                "priority": "Priority",
                "reasoning": "Reasoning",
            },
        },
        "agent": {
            "max_jobs": 10,
            "memory_bank": "",
            "search_buffer": 5,
            "batch_size": 3,
            "batch_delay_seconds": 15,
        },
    }


@pytest.fixture
def sample_resume():
    return {
        "basics": {
            "name": "Jane Doe",
            "email": "jane@example.com",
            "phone": "555-1234",
            "location": "Montreal, QC",
        },
        "work": [
            {
                "company": "Acme Corp",
                "position": "Software Engineer",
                "startDate": "2022-01",
                "endDate": "",
                "description": "Built internal tools.",
                "highlights": ["Built a pipeline that reduced latency by 30%."],
            }
        ],
        "education": [],
        "skills": [{"name": "Languages", "keywords": ["Python", "TypeScript"]}],
        "projects": [],
        "certificates": [],
    }
