from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional

from candidate_profile import load_candidate_profile
from field_mapper import get_value, map_field, validate_value, normalize_text


JS_FIELD_METADATA = r"""
el => {
  const textOf = (node) => {
    if (!node) return '';
    if (node.innerText) return node.innerText.trim();
    if (node.textContent) return node.textContent.trim();
    return '';
  };

  const collectLabels = () => {
    const labels = [];

    if (el.labels) {
      for (const label of Array.from(el.labels)) {
        const labelText = textOf(label);
        if (labelText) labels.push(labelText);
      }
    }

    const ariaLabel = el.getAttribute('aria-label');
    if (ariaLabel) labels.push(ariaLabel.trim());

    const ariaLabelledBy = el.getAttribute('aria-labelledby');
    if (ariaLabelledBy) {
      for (const refId of ariaLabelledBy.split(/\s+/)) {
        const ref = document.getElementById(refId);
        const labelText = textOf(ref);
        if (labelText) labels.push(labelText);
      }
    }

    const fieldset = el.closest('fieldset');
    if (fieldset) {
      const legend = fieldset.querySelector('legend');
      const legendText = textOf(legend);
      if (legendText) labels.push(legendText);
    }

    const closestLabel = el.closest('label');
    const closestLabelText = textOf(closestLabel);
    if (closestLabelText) labels.push(closestLabelText);

    return labels.filter(Boolean);
  };

  const optionItems = [];
  if (el.tagName && el.tagName.toLowerCase() === 'select') {
    for (const option of Array.from(el.options || [])) {
      const optionText = textOf(option) || option.label || option.value || '';
      if (optionText) {
        optionItems.push({
          label: optionText.trim(),
          value: option.value || optionText.trim(),
          selected: !!option.selected,
          disabled: !!option.disabled
        });
      }
    }
  }

  const parent = el.closest('fieldset, .jobs-easy-apply-form-element, .artdeco-form-group, li, div');
  const parentText = textOf(parent).slice(0, 500);

  return {
    tag_name: (el.tagName || '').toLowerCase(),
    type: (el.getAttribute('type') || el.type || '').toLowerCase(),
    name: el.getAttribute('name') || '',
    id: el.id || '',
    placeholder: el.getAttribute('placeholder') || '',
    autocomplete: el.getAttribute('autocomplete') || '',
    title: el.getAttribute('title') || '',
    aria_label: el.getAttribute('aria-label') || '',
    required: !!(el.required || el.getAttribute('aria-required') === 'true'),
    disabled: !!el.disabled,
    checked: !!el.checked,
    value: el.value || '',
    labels: collectLabels(),
    options: optionItems,
    parent_text: parentText
  };
}
"""


@dataclass
class FormField:
    label: str
    placeholder: str
    field_type: str
    available_options: List[str]
    required: bool
    selector: str
    index: int
    dom_type: str
    profile_key: Optional[str] = None
    confidence: float = 0.0
    value: Any = None
    status: str = "unknown"
    reason: str = ""
    raw: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = asdict(self)
        if payload.get("raw") is None:
            payload.pop("raw", None)
        return payload


class EasyApplyAnalyzer:
    """Inspect LinkedIn Easy Apply forms and classify supported fields."""

    ROOT_SELECTORS = [
        ".jobs-easy-apply-modal",
        ".artdeco-modal__content",
        ".jobs-easy-apply-content",
        "form",
    ]

    INPUT_SELECTORS = [
        "input:not([type='hidden']):not([type='button']):not([type='submit']):not([type='reset'])",
        "textarea",
        "select",
        "input[type='radio']",
        "input[type='checkbox']",
    ]

    def __init__(self, confidence_threshold: float = 0.82):
        self.confidence_threshold = confidence_threshold

    def find_scope_selector(self, page) -> str:
        for selector in self.ROOT_SELECTORS:
            try:
                locator = page.locator(selector)
                if locator.count() > 0 and locator.first.is_visible():
                    return selector
            except Exception:
                continue
        return "body"

    def _page_locator(self, page, scope_selector: str, selector: str):
        if scope_selector == "body":
            return page.locator(selector)
        return page.locator(f"{scope_selector} {selector}")

    def _extract_fields_for_selector(self, page, scope_selector: str, selector: str, dom_type: str) -> List[Dict[str, Any]]:
        fields: List[Dict[str, Any]] = []
        locator = self._page_locator(page, scope_selector, selector)

        try:
            count = locator.count()
        except Exception:
            return fields

        for index in range(count):
            item = locator.nth(index)
            try:
                if not item.is_visible():
                    continue
                metadata = item.evaluate(JS_FIELD_METADATA)
                metadata["selector"] = selector
                metadata["index"] = index
                metadata["dom_type"] = dom_type
                fields.append(metadata)
            except Exception:
                continue

        return fields

    def _extract_grouped_choices(self, page, scope_selector: str, selector: str, dom_type: str) -> List[Dict[str, Any]]:
        grouped: Dict[str, Dict[str, Any]] = {}
        locator = self._page_locator(page, scope_selector, selector)

        try:
            count = locator.count()
        except Exception:
            return []

        for index in range(count):
            item = locator.nth(index)
            try:
                if not item.is_visible():
                    continue
                metadata = item.evaluate(JS_FIELD_METADATA)
            except Exception:
                continue

            group_key = metadata.get("name") or normalize_text(" ".join(metadata.get("labels", []))) or f"{selector}:{index}"
            group = grouped.setdefault(
                group_key,
                {
                    "selector": selector,
                    "index": index,
                    "dom_type": dom_type,
                    "name": metadata.get("name", ""),
                    "label": "",
                    "placeholder": "",
                    "required": bool(metadata.get("required")),
                    "options": [],
                    "raw_items": [],
                },
            )

            option_label = metadata.get("labels", [])
            option_text = option_label[0] if option_label else metadata.get("aria_label") or metadata.get("title") or metadata.get("value") or ""
            if option_text:
                group["options"].append(option_text)
            if not group["label"]:
                group["label"] = metadata.get("parent_text") or option_text
            group["raw_items"].append(metadata)
            group["required"] = group["required"] or bool(metadata.get("required"))

        return list(grouped.values())

    def _field_search_text(self, field: Dict[str, Any]) -> str:
        parts = [
            field.get("label", ""),
            field.get("placeholder", ""),
            field.get("name", ""),
            field.get("aria_label", ""),
            field.get("title", ""),
            field.get("autocomplete", ""),
            field.get("parent_text", ""),
            " ".join(field.get("options", []) or []),
        ]
        return " ".join(part for part in parts if part).strip()

    def extract_fields(self, page) -> List[Dict[str, Any]]:
        scope_selector = self.find_scope_selector(page)
        fields: List[Dict[str, Any]] = []

        for selector in self.INPUT_SELECTORS:
            if selector == "input[type='radio']":
                fields.extend(self._extract_grouped_choices(page, scope_selector, selector, "radio"))
                continue
            if selector == "input[type='checkbox']":
                fields.extend(self._extract_grouped_choices(page, scope_selector, selector, "checkbox"))
                continue
            dom_type = "textarea" if "textarea" in selector else "select" if selector == "select" else "input"
            fields.extend(self._extract_fields_for_selector(page, scope_selector, selector, dom_type))

        deduped: List[Dict[str, Any]] = []
        seen = set()
        for field in fields:
            key = (
                field.get("selector", ""),
                field.get("index", 0),
                field.get("dom_type", ""),
                normalize_text(field.get("name", "")),
                normalize_text(field.get("label", "")),
                tuple(normalize_text(option) for option in field.get("options", []) or []),
            )
            if key in seen:
                continue
            seen.add(key)
            deduped.append(field)

        return deduped

    def analyze(self, page, job_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Return a summary describing the visible Easy Apply form."""
        profile = load_candidate_profile()
        scope_selector = self.find_scope_selector(page)
        fields = self.extract_fields(page)
        analyzed_fields: List[FormField] = []
        fillable_fields: List[Dict[str, Any]] = []
        missing_fields: List[str] = []
        unknown_fields: List[str] = []
        confidence_scores: List[float] = []

        for field in fields:
            label = field.get("label") or field.get("name") or field.get("aria_label") or ""
            placeholder = field.get("placeholder") or ""
            dom_type = field.get("dom_type") or field.get("type") or ""
            options = field.get("options") or []
            stored_answer = profile.get_answer_for_label(label) if label else None

            mapping = map_field(label, placeholder=placeholder, field_type=dom_type, options=options)
            print(
                f"[MAPPER] {label or '(unlabeled)'} -> {mapping.get('field_type')} "
                f"| profile={mapping.get('profile_key')} "
                f"| confidence={float(mapping.get('confidence', 0.0)):.2f}"
            )
            value = get_value(mapping["field_type"], label=label, placeholder=placeholder, options=options)
            if stored_answer is not None:
                value = stored_answer
            valid_value = validate_value(mapping["field_type"], value)

            status = "unknown"
            if valid_value and (stored_answer is not None or mapping["field_type"] not in {"unknown", "free_text"}):
                status = "fillable"
                confidence = 1.0 if stored_answer is not None else float(mapping.get("confidence", 0.0))
                confidence_scores.append(confidence)
                fillable_fields.append(
                    {
                        "label": label,
                        "profile_key": mapping.get("profile_key"),
                        "field_type": mapping.get("field_type"),
                        "value": value,
                        "confidence": confidence,
                        "selector": field.get("selector"),
                        "index": field.get("index"),
                        "dom_type": dom_type,
                        "options": options,
                    }
                )
            elif mapping["field_type"] in {"unknown", "free_text"}:
                status = "unknown"
                if label:
                    unknown_fields.append(label)
            elif field.get("required"):
                status = "missing"
                if label:
                    missing_fields.append(label)

            analyzed = FormField(
                label=label,
                placeholder=placeholder,
                field_type=mapping.get("field_type", "unknown"),
                available_options=list(options),
                required=bool(field.get("required")),
                selector=field.get("selector", ""),
                index=int(field.get("index", 0)),
                dom_type=dom_type,
                profile_key=mapping.get("profile_key"),
                confidence=float(mapping.get("confidence", 0.0)),
                value=value if valid_value else None,
                status=status,
                reason=mapping.get("reason", ""),
                raw=field,
            )
            analyzed_fields.append(analyzed)
            print(f"[FIELD] {label or '(unlabeled)'} -> {status}")

        autofill_confidence = round(sum(confidence_scores) / len(confidence_scores), 2) if confidence_scores else 0.0

        summary = {
            "job_title": (job_data or {}).get("title", "Unknown"),
            "company": (job_data or {}).get("company", "Unknown"),
            "fillable_fields": [item["label"] for item in fillable_fields],
            "missing_fields": missing_fields,
            "unknown_fields": unknown_fields,
            "autofill_confidence": autofill_confidence,
            "field_count": len(analyzed_fields),
            "fields": [field.to_dict() for field in analyzed_fields],
            "pending_answers": len(profile.pending_applications),
            "scope_selector": scope_selector,
        }

        return summary


def analyze_easy_apply_form(page, job_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Convenience wrapper used by the apply flow."""
    return EasyApplyAnalyzer().analyze(page, job_data=job_data)
