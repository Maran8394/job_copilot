import re
from difflib import SequenceMatcher
from typing import Any, Dict, Iterable, Optional

from candidate_profile import CandidateProfile, load_candidate_profile


PROFILE_FIELDS = {
    "name": "full_name",
    "first_name": "first_name",
    "last_name": "last_name",
    "email": "email",
    "phone": "phone",
    "location": "location",
    "linkedin_url": "linkedin_url",
    "github_url": "github_url",
    "portfolio_url": "portfolio_url",
    "years_experience": "total_experience_years",
    "salary": "expected_salary",
    "notice_period": "notice_period_days",
    "sponsorship": "requires_sponsorship",
    "work_authorization": "work_authorized",
    "relocation": "willing_to_relocate",
    "education": "education",
    "graduation_year": "graduation_year",
}

SKILL_ENV_KEYS = CandidateProfile.SKILL_ENV_KEYS


def normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", str(value).strip().lower())).strip()


def _best_ratio(text: str, candidates: Iterable[str]) -> float:
    best = 0.0
    for candidate in candidates:
        ratio = SequenceMatcher(None, text, normalize_text(candidate)).ratio()
        if ratio > best:
            best = ratio
    return best


def _match_skill_key(text: str) -> Optional[str]:
    skill_aliases = {
        "python": ["python", "py"],
        "flutter": ["flutter"],
        "dart": ["dart"],
        "sql": ["sql", "postgres", "postgresql", "mysql"],
        "docker": ["docker", "container"],
        "aws": ["aws", "amazon web services"],
        "machine_learning": ["machine learning", "ml"],
        "deep_learning": ["deep learning", "dl", "neural network", "neural networks"],
    }

    for skill, aliases in skill_aliases.items():
        for alias in aliases:
            if re.search(rf"\b{re.escape(alias)}\b", text):
                return SKILL_ENV_KEYS[skill]
    return None


def _match_boolean_question(text: str, phrases: Iterable[str]) -> bool:
    for phrase in phrases:
        if phrase in text:
            return True
    return False


def map_field(label: str, placeholder: str = "", field_type: str = "", options: Optional[Iterable[str]] = None) -> Dict[str, Any]:
    """Classify a field label and map it to a candidate profile value."""
    raw = " ".join(part for part in [label or "", placeholder or "", " ".join(options or [])] if part)
    text = normalize_text(raw)
    mapped: Dict[str, Any] = {
        "field_type": "unknown",
        "profile_key": None,
        "confidence": 0.0,
        "reason": "no match",
    }

    if not text:
        return mapped

    boolean_options = {normalize_text(option) for option in (options or [])}
    has_yes_no = {"yes", "no"}.issubset(boolean_options)

    direct_patterns = [
        ("first_name", ["first name", "given name", "forename"], "first_name"),
        ("last_name", ["last name", "surname", "family name"], "last_name"),
        ("name", ["full name", "your name", "legal name", "candidate name"], "full_name"),
        ("current_title", ["current title", "job title", "current job title", "current role"], "current_title"),
        ("current_company", ["current company", "company name", "current employer", "employer"], "current_company"),
        ("email", ["email", "email address", "e mail"], "email"),
        ("phone", ["phone", "mobile", "cell", "telephone"], "phone"),
        ("location", ["location", "current location", "city", "country", "residence"], "location"),
        ("linkedin_url", ["linkedin", "linkedin profile", "linkedin url", "linkedin url or profile"], "linkedin_url"),
        ("github_url", ["github", "github url", "github profile"], "github_url"),
        ("portfolio_url", ["portfolio", "website", "personal site", "personal website", "url"], "portfolio_url"),
        ("education", ["education", "highest degree", "degree", "school", "university", "college"], "education"),
        ("graduation_year", ["graduation year", "year of graduation", "year graduated"], "graduation_year"),
        ("notice_period", ["notice period", "available to start", "start date", "when can you start", "join date"], "notice_period_days"),
        ("salary", ["current salary", "expected salary", "desired salary", "salary expectation", "compensation", "pay"], "expected_salary"),
        ("work_authorization", ["work authorization", "work authorised", "work authorized", "legally authorized", "eligible to work", "authorized to work"], "work_authorized"),
        ("sponsorship", ["sponsorship", "visa sponsorship", "require sponsorship", "need sponsorship"], "requires_sponsorship"),
        ("relocation", ["relocate", "relocation", "willing to relocate", "open to relocate", "move to"], "willing_to_relocate"),
    ]

    for field_name, phrases, profile_key in direct_patterns:
        if _match_boolean_question(text, phrases):
            mapped.update({
                "field_type": field_name,
                "profile_key": profile_key,
                "confidence": 0.97,
                "reason": f"matched {field_name}",
            })
            return mapped

    if "year" in text and "experience" in text:
        skill_key = _match_skill_key(text)
        if skill_key:
            mapped.update({
                "field_type": "skill_experience",
                "profile_key": skill_key,
                "confidence": 0.98,
                "reason": f"skill match {skill_key}",
            })
            return mapped

        mapped.update({
            "field_type": "years_experience",
            "profile_key": "total_experience_years",
            "confidence": 0.9,
            "reason": "matched generic experience question",
        })
        return mapped

    if _match_boolean_question(text, ["how many years", "years of experience", "experience years", "total years"]):
        skill_key = _match_skill_key(text)
        if skill_key:
            mapped.update({
                "field_type": "skill_experience",
                "profile_key": skill_key,
                "confidence": 0.95,
                "reason": f"skill match {skill_key}",
            })
            return mapped

        mapped.update({
            "field_type": "years_experience",
            "profile_key": "total_experience_years",
            "confidence": 0.85,
            "reason": "matched experience question",
        })
        return mapped

    if any(word in text for word in ["cover letter", "why do you want", "tell us about", "describe", "additional information", "short answer", "free text", "essay"]):
        mapped.update({
            "field_type": "free_text",
            "profile_key": None,
            "confidence": 0.82,
            "reason": "free-text prompt",
        })
        return mapped

    # Checkbox and radio answers frequently appear as yes/no options with a text label.
    if field_type in {"checkbox", "radio"} and has_yes_no:
        if _match_boolean_question(text, ["authorized", "sponsorship", "relocate", "relocation", "willing", "eligible", "work"]):
            mapped.update({
                "field_type": "work_authorization" if "authorized" in text or "eligible" in text or "work" in text else "relocation",
                "profile_key": "work_authorized" if "authorized" in text or "eligible" in text or "work" in text else "willing_to_relocate",
                "confidence": 0.87,
                "reason": "binary option match",
            })
            return mapped

    if field_type == "select" and options:
        option_text = " ".join(normalize_text(option) for option in options)
        if "yes" in option_text and "no" in option_text:
            if "sponsorship" in text or "visa" in text:
                mapped.update({
                    "field_type": "sponsorship",
                    "profile_key": "requires_sponsorship",
                    "confidence": 0.9,
                    "reason": "yes/no sponsorship dropdown",
                })
                return mapped
            if "authorize" in text or "eligible" in text or "work" in text:
                mapped.update({
                    "field_type": "work_authorization",
                    "profile_key": "work_authorized",
                    "confidence": 0.9,
                    "reason": "yes/no work authorization dropdown",
                })
                return mapped
            if "relocate" in text:
                mapped.update({
                    "field_type": "relocation",
                    "profile_key": "willing_to_relocate",
                    "confidence": 0.9,
                    "reason": "yes/no relocation dropdown",
                })
                return mapped

    fuzzy_targets = {
        "name": ["full name", "name"],
        "email": ["email address", "email"],
        "phone": ["phone number", "phone"],
        "location": ["current location", "location"],
        "linkedin_url": ["linkedin profile", "linkedin"],
        "github_url": ["github profile", "github"],
        "portfolio_url": ["portfolio", "website", "personal site"],
        "education": ["education", "degree", "school"],
        "years_experience": ["years of experience", "experience"],
        "salary": ["salary", "compensation"],
        "notice_period": ["notice period", "available to start"],
        "sponsorship": ["visa sponsorship", "sponsorship"],
        "work_authorization": ["work authorization", "eligible to work"],
        "relocation": ["relocate", "relocation"],
    }

    for field_name, phrases in fuzzy_targets.items():
        ratio = _best_ratio(text, phrases)
        if ratio >= 0.78:
            profile_key = PROFILE_FIELDS.get(field_name)
            confidence = min(0.95, round(ratio, 2))
            mapped.update({
                "field_type": field_name,
                "profile_key": profile_key,
                "confidence": confidence,
                "reason": f"fuzzy match {ratio:.2f}",
            })
            return mapped

    return mapped


def get_value(field_type: str, label: str = "", placeholder: str = "", options: Optional[Iterable[str]] = None) -> Any:
    """Return the best candidate value for a field type."""
    profile = load_candidate_profile()
    mapping = map_field(label, placeholder=placeholder, field_type=field_type, options=options)
    profile_key = mapping.get("profile_key")

    if label:
        exact_answer = profile.get_answer_for_label(label)
        if exact_answer:
            return exact_answer

    if field_type == "skill_experience":
        if profile_key:
            for skill_name, env_key in SKILL_ENV_KEYS.items():
                if env_key == profile_key:
                    return profile.get_skill_year(skill_name)
        return None

    if field_type == "years_experience":
        return profile.get_value("total_experience_years")

    if profile_key:
        return profile.get_value(profile_key)

    return None


def validate_value(field_type: str, value: Any) -> bool:
    """Validate a value before attempting to fill it."""
    if value is None:
        return False

    if isinstance(value, str):
        value = value.strip()
        if not value:
            return False

    if field_type in {"name", "first_name", "last_name", "current_title", "current_company", "location", "education", "free_text"}:
        return bool(str(value).strip())

    if field_type in {"email"}:
        return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", str(value).strip()))

    if field_type in {"phone"}:
        compact = re.sub(r"[^\d+]", "", str(value))
        return len(re.sub(r"\D", "", compact)) >= 7

    if field_type in {"linkedin_url", "github_url", "portfolio_url"}:
        text = str(value).strip()
        return bool(re.search(r"\b[a-z0-9.-]+\.[a-z]{2,}\b", text, re.I))

    if field_type in {"years_experience", "skill_experience", "salary", "notice_period", "graduation_year"}:
        try:
            float(str(value).replace(",", "").replace("k", "000").strip().lower())
            return True
        except ValueError:
            return False

    if field_type in {"sponsorship", "work_authorization", "relocation"}:
        return isinstance(value, bool) or str(value).strip().lower() in {"yes", "no", "true", "false", "1", "0"}

    return bool(str(value).strip())
