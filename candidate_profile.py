import json
import os
import re
from pathlib import Path
from typing import Any, Dict, Optional

from dotenv import load_dotenv


load_dotenv()

PROFILE_FILE = Path("candidate_profile.json")


def _parse_bool(value: Any) -> Optional[bool]:
    if value is None:
        return None

    if isinstance(value, bool):
        return value

    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return None


def _parse_number(value: Any) -> Optional[Any]:
    if value is None:
        return None

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value

    text = str(value).strip()
    if not text:
        return None

    compact = text.replace(",", "").strip().lower()

    # Accept simple salary shorthand such as 120k.
    salary_match = re.fullmatch(r"(\d+(?:\.\d+)?)(k)?", compact)
    if salary_match:
        number = float(salary_match.group(1))
        if salary_match.group(2):
            number *= 1000
        if number.is_integer():
            return int(number)
        return number

    try:
        number = float(compact)
    except ValueError:
        return None

    if number.is_integer():
        return int(number)
    return number


def _normalize_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(value).strip().lower()).strip("_")


class CandidateProfile:
    """Loads candidate profile data from environment variables and JSON storage."""

    CORE_FIELDS = {
        "full_name",
        "first_name",
        "last_name",
        "email",
        "phone",
        "location",
        "linkedin_url",
        "github_url",
        "portfolio_url",
        "total_experience_years",
        "current_title",
        "current_company",
        "current_salary",
        "expected_salary",
        "notice_period_days",
        "work_authorized",
        "requires_sponsorship",
        "willing_to_relocate",
        "education",
        "graduation_year",
        "skills",
    }

    BOOLEAN_FIELDS = {
        "work_authorized",
        "requires_sponsorship",
        "willing_to_relocate",
    }

    NUMBER_FIELDS = {
        "total_experience_years",
        "current_salary",
        "expected_salary",
        "notice_period_days",
        "graduation_year",
    }

    URL_FIELDS = {
        "linkedin_url",
        "github_url",
        "portfolio_url",
    }

    SKILL_ENV_KEYS = {
        "python": "PYTHON_YEARS",
        "flutter": "FLUTTER_YEARS",
        "dart": "DART_YEARS",
        "sql": "SQL_YEARS",
        "docker": "DOCKER_YEARS",
        "aws": "AWS_YEARS",
        "machine_learning": "MACHINE_LEARNING_YEARS",
        "deep_learning": "DEEP_LEARNING_YEARS",
    }

    def __init__(self, profile_path: Path | str = PROFILE_FILE):
        self.profile_path = Path(profile_path)
        self.raw_data: Dict[str, Any] = {}
        self.extra_data: Dict[str, Any] = {}
        self.answers: Dict[str, str] = {}
        self.pending_applications: Dict[str, Dict[str, Any]] = {}
        self.skill_years: Dict[str, Any] = {}

        self.full_name: Optional[str] = None
        self.first_name: Optional[str] = None
        self.last_name: Optional[str] = None
        self.email: Optional[str] = None
        self.phone: Optional[str] = None
        self.location: Optional[str] = None
        self.linkedin_url: Optional[str] = None
        self.github_url: Optional[str] = None
        self.portfolio_url: Optional[str] = None
        self.total_experience_years: Optional[Any] = None
        self.current_title: Optional[str] = None
        self.current_company: Optional[str] = None
        self.current_salary: Optional[Any] = None
        self.expected_salary: Optional[Any] = None
        self.notice_period_days: Optional[Any] = None
        self.work_authorized: Optional[bool] = None
        self.requires_sponsorship: Optional[bool] = None
        self.willing_to_relocate: Optional[bool] = None
        self.education: Optional[str] = None
        self.graduation_year: Optional[Any] = None
        self.skills: Any = []

        self.load()

    def load(self) -> "CandidateProfile":
        """Load JSON profile data and apply environment overrides."""
        self.raw_data = self._load_json()
        self.extra_data = {
            key: value
            for key, value in self.raw_data.items()
            if key not in self.CORE_FIELDS and key not in {"skill_years", "answers", "pending_applications"}
        }

        self.answers = self._coerce_answers(self.raw_data.get("answers", {}))
        self.pending_applications = self.raw_data.get("pending_applications", {}) or {}
        self.skill_years = self._load_skill_years()

        for field in self.CORE_FIELDS:
            if field in {"skills"}:
                continue
            setattr(self, field, self._coerce_json_value(field, self.raw_data.get(field)))

        self.skills = self._coerce_skills(self.raw_data.get("skills"))
        self._apply_env_overrides()
        self._derive_name_fields()
        return self

    def _load_json(self) -> Dict[str, Any]:
        if not self.profile_path.exists():
            return {}

        try:
            with self.profile_path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                return data if isinstance(data, dict) else {}
        except Exception as exc:
            print(f"[PROFILE] Failed to load {self.profile_path}: {exc}")
            return {}

    def _coerce_answers(self, value: Any) -> Dict[str, str]:
        if not isinstance(value, dict):
            return {}

        normalized: Dict[str, str] = {}
        for key, answer in value.items():
            if answer is None:
                continue
            normalized[_normalize_key(key)] = str(answer).strip()
        return normalized

    def _coerce_skills(self, value: Any) -> Any:
        if isinstance(value, list):
            return value
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, dict):
            return value
        return []

    def _coerce_json_value(self, field: str, value: Any) -> Any:
        if value is None:
            return None

        if field in self.BOOLEAN_FIELDS:
            return _parse_bool(value)
        if field in self.NUMBER_FIELDS:
            return _parse_number(value)
        if field in self.URL_FIELDS:
            text = str(value).strip()
            return text or None
        if field == "skills":
            return self._coerce_skills(value)

        text = str(value).strip()
        return text or None

    def _load_skill_years(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {}
        for skill, env_key in self.SKILL_ENV_KEYS.items():
            env_value = os.getenv(env_key)
            if env_value is not None and str(env_value).strip():
                result[skill] = _parse_number(env_value)

        raw_skill_years = self.raw_data.get("skill_years", {})
        if isinstance(raw_skill_years, dict):
            for key, value in raw_skill_years.items():
                normalized = _normalize_key(key)
                parsed = _parse_number(value)
                result[normalized] = parsed if parsed is not None else value

        return result

    def _apply_env_overrides(self) -> None:
        env_map = {
            "full_name": "FULL_NAME",
            "first_name": "FIRST_NAME",
            "last_name": "LAST_NAME",
            "email": "EMAIL",
            "phone": "PHONE",
            "location": "LOCATION",
            "linkedin_url": "LINKEDIN_URL",
            "github_url": "GITHUB_URL",
            "portfolio_url": "PORTFOLIO_URL",
            "total_experience_years": "TOTAL_EXPERIENCE_YEARS",
            "current_title": "CURRENT_TITLE",
            "current_company": "CURRENT_COMPANY",
            "current_salary": "CURRENT_SALARY",
            "expected_salary": "EXPECTED_SALARY",
            "notice_period_days": "NOTICE_PERIOD_DAYS",
            "work_authorized": "WORK_AUTHORIZED",
            "requires_sponsorship": "REQUIRES_SPONSORSHIP",
            "willing_to_relocate": "WILLING_TO_RELOCATE",
            "education": "EDUCATION",
            "graduation_year": "GRADUATION_YEAR",
        }

        for field, env_key in env_map.items():
            env_value = os.getenv(env_key)
            if env_value is None or not str(env_value).strip():
                continue
            setattr(self, field, self._coerce_env_value(field, env_value))

        # Update skill experience overrides from environment.
        for skill, env_key in self.SKILL_ENV_KEYS.items():
            env_value = os.getenv(env_key)
            if env_value is None or not str(env_value).strip():
                continue
            self.skill_years[skill] = _parse_number(env_value)

    def _coerce_env_value(self, field: str, value: Any) -> Any:
        if field in self.BOOLEAN_FIELDS:
            return _parse_bool(value)
        if field in self.NUMBER_FIELDS:
            return _parse_number(value)

        text = str(value).strip()
        return text or None

    def _derive_name_fields(self) -> None:
        if self.full_name and (not self.first_name or not self.last_name):
            parts = [part for part in re.split(r"\s+", str(self.full_name).strip()) if part]
            if parts and not self.first_name:
                self.first_name = parts[0]
            if len(parts) > 1 and not self.last_name:
                self.last_name = " ".join(parts[1:])

        if not self.full_name and self.first_name and self.last_name:
            self.full_name = f"{self.first_name} {self.last_name}".strip()

    def get_value(self, field_name: str) -> Any:
        """Return a field value by canonical field name."""
        if field_name == "skills":
            return self.skills
        if field_name == "skill_years":
            return self.skill_years
        if field_name == "answers":
            return self.answers
        return getattr(self, field_name, None)

    def get_skill_year(self, skill_name: str) -> Any:
        normalized = _normalize_key(skill_name)
        if normalized in self.skill_years:
            return self.skill_years[normalized]
        return None

    def get_answer_for_label(self, label: str) -> Optional[str]:
        return self.answers.get(_normalize_key(label))

    def set_answer_for_label(self, label: str, value: Any) -> None:
        normalized = _normalize_key(label)
        self.answers[normalized] = str(value).strip()

    def update_custom_answers(self, job_id: Any, answers: Dict[str, Any], report: Optional[Dict[str, Any]] = None) -> None:
        for label, value in answers.items():
            self.set_answer_for_label(label, value)

        if job_id is not None:
            job_key = str(job_id)
            pending_entry = self.pending_applications.get(job_key, {})
            pending_entry.setdefault("job_id", job_key)
            if report:
                pending_entry.update(report)
            pending_entry["answers"] = {str(k): str(v).strip() for k, v in answers.items()}
            self.pending_applications[job_key] = pending_entry

        self.save()

    def store_pending_application(self, job_id: Any, report: Dict[str, Any]) -> None:
        if job_id is None:
            return

        job_key = str(job_id)
        existing = self.pending_applications.get(job_key, {})
        merged = {**existing, **report}
        merged["job_id"] = job_key
        self.pending_applications[job_key] = merged
        self.save()

    def clear_pending_application(self, job_id: Any) -> None:
        if job_id is None:
            return

        self.pending_applications.pop(str(job_id), None)
        self.save()

    def to_dict(self) -> Dict[str, Any]:
        data = {
            "full_name": self.full_name,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "email": self.email,
            "phone": self.phone,
            "location": self.location,
            "linkedin_url": self.linkedin_url,
            "github_url": self.github_url,
            "portfolio_url": self.portfolio_url,
            "total_experience_years": self.total_experience_years,
            "current_title": self.current_title,
            "current_company": self.current_company,
            "current_salary": self.current_salary,
            "expected_salary": self.expected_salary,
            "notice_period_days": self.notice_period_days,
            "work_authorized": self.work_authorized,
            "requires_sponsorship": self.requires_sponsorship,
            "willing_to_relocate": self.willing_to_relocate,
            "education": self.education,
            "graduation_year": self.graduation_year,
            "skills": self.skills,
            "skill_years": self.skill_years,
            "answers": self.answers,
            "pending_applications": self.pending_applications,
        }
        data.update(self.extra_data)
        return data

    def save(self) -> None:
        """Persist the profile JSON."""
        try:
            self.profile_path.write_text(
                json.dumps(self.to_dict(), indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as exc:
            print(f"[PROFILE] Failed to save {self.profile_path}: {exc}")


def load_candidate_profile() -> CandidateProfile:
    """Convenience loader used by other modules."""
    return CandidateProfile()
