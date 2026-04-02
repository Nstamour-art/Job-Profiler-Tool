"""
Resume YAML editor tools for the job search agent.

Provides read_resume_section and write_resume_section as LangChain tools
that operate on one section of resume.yaml at a time.

The agent MUST present the proposed change to the user and receive explicit
confirmation before calling write_resume_section.
"""

from __future__ import annotations

import yaml
from langchain_core.tools import tool


VALID_SECTIONS = frozenset({"basics", "work", "education", "skills", "projects", "certificates"})


def create_resume_tools(resume_path: str):
    """Return (read_resume_section, write_resume_section) LangChain tools bound to resume_path."""

    @tool
    def read_resume_section(section: str) -> str:
        """Read a single section of the candidate's resume YAML.

        Args:
            section: One of: basics, work, education, skills, projects, certificates.

        Returns:
            The section content as a YAML string, or an error message.
        """
        if section not in VALID_SECTIONS:
            return f"Invalid section '{section}'. Valid sections: {', '.join(sorted(VALID_SECTIONS))}"
        with open(resume_path, encoding="utf-8") as f:
            resume = yaml.safe_load(f)
        content = resume.get(section, [])
        return yaml.dump(content, allow_unicode=True)

    @tool
    def write_resume_section(section: str, new_content: str) -> str:
        """Overwrite a single section of the candidate's resume YAML.

        IMPORTANT: Always show the user the proposed change and get explicit
        confirmation ('yes') before calling this tool.

        Args:
            section: One of: basics, work, education, skills, projects, certificates.
            new_content: The new section content as a YAML string.

        Returns:
            A confirmation message or an error message.
        """
        if section not in VALID_SECTIONS:
            return f"Invalid section '{section}'. Valid sections: {', '.join(sorted(VALID_SECTIONS))}"
        try:
            parsed = yaml.safe_load(new_content)
        except yaml.YAMLError as e:
            return f"Invalid YAML: {e}"

        if parsed is None:
            return "New content is empty — section not written."

        with open(resume_path, encoding="utf-8") as f:
            resume = yaml.safe_load(f)

        resume[section] = parsed

        with open(resume_path, "w", encoding="utf-8") as f:
            yaml.dump(resume, f, allow_unicode=True, default_flow_style=False)

        return f"resume.yaml updated: '{section}' section replaced successfully."

    return read_resume_section, write_resume_section
