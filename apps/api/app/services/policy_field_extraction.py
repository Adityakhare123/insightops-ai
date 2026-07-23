from __future__ import annotations

import re
from dataclasses import asdict, dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Callable, Iterable, TypeAlias


ExtractedValue: TypeAlias = (
    str
    | int
    | float
    | bool
    | None
)

FieldNormalizer: TypeAlias = Callable[
    [str],
    ExtractedValue,
]


@dataclass(
    frozen=True,
    slots=True,
)
class PolicySourcePage:
    """
    Represents OCR or extracted text from one document page.
    """

    page_number: int
    text: str
    confidence_score: float | None = None

    def __post_init__(self) -> None:
        if self.page_number < 1:
            raise ValueError(
                "page_number must be at least 1."
            )

        if (
            self.confidence_score is not None
            and not (
                0
                <= self.confidence_score
                <= 1
            )
        ):
            raise ValueError(
                "confidence_score must be "
                "between 0 and 1."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class ExtractedPolicyField:
    """
    Stores one normalized field and its source evidence.
    """

    name: str
    value: ExtractedValue
    raw_value: str | None

    found: bool

    page_number: int | None
    source_text: str | None

    confidence_score: float | None
    extraction_method: str | None

    def to_dict(
        self,
    ) -> dict[str, object]:
        return asdict(self)


@dataclass(
    frozen=True,
    slots=True,
)
class PolicyDocumentExtraction:
    """
    Complete normalized policy-document extraction.
    """

    fields: dict[
        str,
        ExtractedPolicyField,
    ]

    warnings: tuple[str, ...]

    document_confidence: float

    page_count: int

    def get_field(
        self,
        field_name: str,
    ) -> ExtractedPolicyField:
        try:
            return self.fields[
                field_name
            ]
        except KeyError as error:
            raise KeyError(
                f"Unknown policy field: "
                f"{field_name}"
            ) from error

    def get_value(
        self,
        field_name: str,
    ) -> ExtractedValue:
        return self.get_field(
            field_name
        ).value

    def to_dict(
        self,
    ) -> dict[str, object]:
        return {
            "fields": {
                field_name:
                    extracted_field.to_dict()
                for (
                    field_name,
                    extracted_field,
                ) in self.fields.items()
            },
            "warnings": list(
                self.warnings
            ),
            "document_confidence":
                self.document_confidence,
            "page_count":
                self.page_count,
        }


@dataclass(
    frozen=True,
    slots=True,
)
class _FieldRule:
    name: str
    labels: tuple[str, ...]

    normalizer: FieldNormalizer

    base_confidence: float

    required: bool = False


@dataclass(
    frozen=True,
    slots=True,
)
class _FieldCandidate:
    field_name: str

    value: ExtractedValue
    raw_value: str

    page_number: int
    source_text: str

    confidence_score: float
    extraction_method: str


def _collapse_whitespace(
    value: str,
) -> str:
    return re.sub(
        r"\s+",
        " ",
        value,
    ).strip()


def _clean_text(
    value: str,
) -> str:
    normalized = value.replace(
        "\u00a0",
        " ",
    )

    normalized = normalized.replace(
        "\r\n",
        "\n",
    )

    normalized = normalized.replace(
        "\r",
        "\n",
    )

    return normalized.strip()


def _strip_trailing_delimiters(
    value: str,
) -> str:
    return value.strip(
        " \t:;|,"
    )


def _normalize_plain_text(
    value: str,
) -> str | None:
    normalized = _collapse_whitespace(
        _strip_trailing_delimiters(
            value
        )
    )

    return normalized or None


def _normalize_policy_number(
    value: str,
) -> str | None:
    normalized = value.upper().strip()

    normalized = re.sub(
        r"\s+",
        "",
        normalized,
    )

    normalized = normalized.strip(
        ":;,.|"
    )

    if len(normalized) < 4:
        return None

    if not re.fullmatch(
        r"[A-Z0-9][A-Z0-9\-_/.]*",
        normalized,
    ):
        return None

    return normalized


def _normalize_person_name(
    value: str,
) -> str | None:
    normalized = _collapse_whitespace(
        value
    )

    normalized = normalized.strip(
        ":;|,"
    )

    if len(normalized) < 2:
        return None

    if not re.search(
        r"[A-Za-z]",
        normalized,
    ):
        return None

    return normalized


_DATE_FORMATS = (
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%m.%d.%Y",
    "%m/%d/%y",
    "%m-%d-%y",
    "%B %d, %Y",
    "%B %d %Y",
    "%b %d, %Y",
    "%b %d %Y",
    "%d %B %Y",
    "%d %b %Y",
)


_DATE_TOKEN_PATTERNS = (
    re.compile(
        r"\b\d{4}-\d{1,2}-\d{1,2}\b"
    ),
    re.compile(
        r"\b\d{1,2}[./-]\d{1,2}"
        r"[./-]\d{2,4}\b"
    ),
    re.compile(
        r"\b(?:January|February|March|April|May|June|"
        r"July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
        r"\s+\d{1,2},?\s+\d{4}\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|"
        r"July|August|September|October|November|December|"
        r"Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)"
        r"\s+\d{4}\b",
        re.IGNORECASE,
    ),
)


def _extract_date_token(
    value: str,
) -> str | None:
    cleaned_value = _collapse_whitespace(
        value
    )

    for pattern in _DATE_TOKEN_PATTERNS:
        match = pattern.search(
            cleaned_value
        )

        if match:
            return match.group(0)

    return cleaned_value or None


def _normalize_date(
    value: str,
) -> str | None:
    date_token = _extract_date_token(
        value
    )

    if not date_token:
        return None

    normalized_token = re.sub(
        r"\bSept\b",
        "Sep",
        date_token,
        flags=re.IGNORECASE,
    )

    for date_format in _DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(
                normalized_token,
                date_format,
            ).date()

            return parsed_date.isoformat()
        except ValueError:
            continue

    return None


def _normalize_money(
    value: str,
) -> str | None:
    cleaned_value = value.strip()

    is_negative = (
        cleaned_value.startswith("(")
        and cleaned_value.endswith(")")
    )

    cleaned_value = cleaned_value.replace(
        "USD",
        "",
    )

    cleaned_value = cleaned_value.replace(
        "usd",
        "",
    )

    cleaned_value = cleaned_value.replace(
        "$",
        "",
    )

    cleaned_value = cleaned_value.replace(
        ",",
        "",
    )

    cleaned_value = cleaned_value.strip(
        " ()"
    )

    amount_match = re.search(
        r"-?\d+(?:\.\d+)?",
        cleaned_value,
    )

    if not amount_match:
        return None

    try:
        amount = Decimal(
            amount_match.group(0)
        )
    except InvalidOperation:
        return None

    if is_negative:
        amount = -abs(amount)

    amount = amount.quantize(
        Decimal("0.01")
    )

    return format(
        amount,
        ".2f",
    )


_STATUS_ALIASES = {
    "active": "active",
    "in force": "active",
    "in-force": "active",
    "issued": "active",
    "cancelled": "cancelled",
    "canceled": "cancelled",
    "terminated": "cancelled",
    "inactive": "cancelled",
    "pending": "pending",
    "pending issue": "pending",
    "not issued": "not_issued",
    "declined": "not_issued",
    "lapsed": "lapsed",
    "pending lapse": "pending_lapse",
    "trumped": "trumped",
}


def _normalize_status(
    value: str,
) -> str | None:
    normalized = _collapse_whitespace(
        value
    ).lower()

    normalized = normalized.strip(
        ":;|,."
    )

    if normalized in _STATUS_ALIASES:
        return _STATUS_ALIASES[
            normalized
        ]

    for (
        status_alias,
        normalized_status,
    ) in _STATUS_ALIASES.items():
        if re.search(
            rf"\b{
                re.escape(status_alias)
            }\b",
            normalized,
        ):
            return normalized_status

    return None


_FIELD_RULES = (
    _FieldRule(
        name="policy_number",
        labels=(
            (
                r"policy\s*"
                r"(?:number|no\.?|#|id)"
            ),
            r"contract\s*(?:number|no\.?|#)",
            r"certificate\s*(?:number|no\.?|#)",
        ),
        normalizer=_normalize_policy_number,
        base_confidence=0.99,
        required=True,
    ),
    _FieldRule(
        name="customer_name",
        labels=(
            (
                r"(?:policyholder|insured|customer|"
                r"member|subscriber)"
                r"(?:\s+name)?"
            ),
        ),
        normalizer=_normalize_person_name,
        base_confidence=0.96,
        required=True,
    ),
    _FieldRule(
        name="carrier_name",
        labels=(
            r"carrier(?:\s+name)?",
            r"insurance\s+company",
            r"company\s+name",
            r"insurer",
        ),
        normalizer=_normalize_plain_text,
        base_confidence=0.94,
    ),
    _FieldRule(
        name="plan_name",
        labels=(
            r"plan(?:\s+name)?",
            r"product(?:\s+name)?",
            r"coverage\s+plan",
        ),
        normalizer=_normalize_plain_text,
        base_confidence=0.94,
    ),
    _FieldRule(
        name="effective_date",
        labels=(
            r"effective\s+date",
            r"policy\s+effective(?:\s+date)?",
            r"coverage\s+effective(?:\s+date)?",
            r"coverage\s+start(?:\s+date)?",
            r"start\s+date",
        ),
        normalizer=_normalize_date,
        base_confidence=0.97,
        required=True,
    ),
    _FieldRule(
        name="termination_date",
        labels=(
            r"termination\s+date",
            r"policy\s+end(?:\s+date)?",
            r"coverage\s+end(?:\s+date)?",
            r"end\s+date",
            r"cancel(?:lation)?\s+date",
        ),
        normalizer=_normalize_date,
        base_confidence=0.96,
    ),
    _FieldRule(
        name="signature_date",
        labels=(
            r"signature\s+date",
            r"signed\s+date",
            r"date\s+signed",
            r"application\s+signed(?:\s+date)?",
        ),
        normalizer=_normalize_date,
        base_confidence=0.96,
    ),
    _FieldRule(
        name="premium",
        labels=(
            r"premium(?:\s+amount)?",
            r"monthly\s+premium",
            r"annual\s+premium",
            r"policy\s+premium",
        ),
        normalizer=_normalize_money,
        base_confidence=0.97,
        required=True,
    ),
    _FieldRule(
        name="policy_status",
        labels=(
            r"policy\s+status",
            r"coverage\s+status",
            r"status",
        ),
        normalizer=_normalize_status,
        base_confidence=0.94,
    ),
)


_FIELD_RULES_BY_NAME = {
    rule.name: rule
    for rule in _FIELD_RULES
}


_FALLBACK_POLICY_NUMBER_PATTERN = re.compile(
    r"(?<![A-Z0-9])"
    r"(?P<value>"
    r"(?:POLICY|CONTRACT|CERT|POL)"
    r"[-\s]?"
    r"(?=[A-Z0-9/_\-.]*\d)"
    r"[A-Z0-9]"
    r"[A-Z0-9/_\-.]{3,}"
    r")"
    r"(?![A-Z0-9])",
    re.IGNORECASE,
)


def _build_label_pattern(
    rule: _FieldRule,
) -> re.Pattern[str]:
    joined_labels = "|".join(
        f"(?:{label})"
        for label in rule.labels
    )

    return re.compile(
        rf"^\s*(?:{joined_labels})"
        rf"\s*(?:[:#=\-]|\bis\b)?"
        rf"\s*(?P<value>.*?)\s*$",
        re.IGNORECASE,
    )


_LABEL_PATTERNS = {
    rule.name:
        _build_label_pattern(
            rule
        )
    for rule in _FIELD_RULES
}


def _calculate_confidence(
    *,
    page_confidence: float | None,
    base_confidence: float,
    next_line_value: bool,
    fallback: bool,
) -> float:
    confidence = base_confidence

    if page_confidence is not None:
        confidence = min(
            confidence,
            page_confidence,
        )

    if next_line_value:
        confidence -= 0.02

    if fallback:
        confidence -= 0.15

    return round(
        max(
            0,
            min(
                confidence,
                1,
            ),
        ),
        4,
    )


def _next_non_empty_line(
    lines: list[str],
    current_index: int,
) -> tuple[str, int] | None:
    for next_index in range(
        current_index + 1,
        min(
            len(lines),
            current_index + 3,
        ),
    ):
        candidate_line = lines[
            next_index
        ].strip()

        if candidate_line:
            return (
                candidate_line,
                next_index,
            )

    return None


def _extract_labeled_candidates(
    page: PolicySourcePage,
    rule: _FieldRule,
    warnings: list[str],
) -> list[_FieldCandidate]:
    candidates: list[
        _FieldCandidate
    ] = []

    lines = _clean_text(
        page.text
    ).splitlines()

    label_pattern = _LABEL_PATTERNS[
        rule.name
    ]

    for line_index, line in enumerate(
        lines
    ):
        clean_line = _collapse_whitespace(
            line
        )

        if not clean_line:
            continue

        match = label_pattern.match(
            clean_line
        )

        if not match:
            continue

        raw_value = _strip_trailing_delimiters(
            match.group(
                "value"
            )
        )

        used_next_line = False
        source_text = clean_line

        if not raw_value:
            next_line_result = (
                _next_non_empty_line(
                    lines,
                    line_index,
                )
            )

            if next_line_result is None:
                continue

            raw_value, next_line_index = (
                next_line_result
            )

            raw_value = _strip_trailing_delimiters(
                raw_value
            )

            source_text = (
                f"{clean_line}\n"
                f"{_collapse_whitespace(
                    lines[next_line_index]
                )}"
            )

            used_next_line = True

        normalized_value = rule.normalizer(
            raw_value
        )

        if normalized_value is None:
            warnings.append(
                (
                    f"Could not normalize "
                    f"{rule.name} value "
                    f"'{raw_value}' on page "
                    f"{page.page_number}."
                )
            )

            continue

        confidence_score = (
            _calculate_confidence(
                page_confidence=(
                    page.confidence_score
                ),
                base_confidence=(
                    rule.base_confidence
                ),
                next_line_value=(
                    used_next_line
                ),
                fallback=False,
            )
        )

        candidates.append(
            _FieldCandidate(
                field_name=rule.name,
                value=normalized_value,
                raw_value=raw_value,
                page_number=(
                    page.page_number
                ),
                source_text=source_text,
                confidence_score=(
                    confidence_score
                ),
                extraction_method=(
                    "labeled_next_line"
                    if used_next_line
                    else "labeled_line"
                ),
            )
        )

    return candidates


def _extract_policy_number_fallback(
    page: PolicySourcePage,
) -> _FieldCandidate | None:
    match = (
        _FALLBACK_POLICY_NUMBER_PATTERN
        .search(
            _clean_text(
                page.text
            )
        )
    )

    if not match:
        return None

    raw_value = match.group(
        "value"
    )

    normalized_value = (
        _normalize_policy_number(
            raw_value
        )
    )

    if normalized_value is None:
        return None

    source_start = max(
        0,
        match.start() - 40,
    )

    source_end = min(
        len(page.text),
        match.end() + 40,
    )

    source_text = _collapse_whitespace(
        page.text[
            source_start:source_end
        ]
    )

    return _FieldCandidate(
        field_name="policy_number",
        value=normalized_value,
        raw_value=raw_value,
        page_number=page.page_number,
        source_text=source_text,
        confidence_score=(
            _calculate_confidence(
                page_confidence=(
                    page.confidence_score
                ),
                base_confidence=0.90,
                next_line_value=False,
                fallback=True,
            )
        ),
        extraction_method=(
            "fallback_pattern"
        ),
    )


def _candidate_sort_key(
    candidate: _FieldCandidate,
) -> tuple[float, int, int]:
    method_priority = {
        "labeled_line": 3,
        "labeled_next_line": 2,
        "fallback_pattern": 1,
    }.get(
        candidate.extraction_method,
        0,
    )

    return (
        candidate.confidence_score,
        method_priority,
        -candidate.page_number,
    )


def _select_candidate(
    *,
    field_name: str,
    candidates: list[_FieldCandidate],
    warnings: list[str],
    minimum_confidence: float,
) -> ExtractedPolicyField:
    if not candidates:
        return ExtractedPolicyField(
            name=field_name,
            value=None,
            raw_value=None,
            found=False,
            page_number=None,
            source_text=None,
            confidence_score=None,
            extraction_method=None,
        )

    selected_candidate = max(
        candidates,
        key=_candidate_sort_key,
    )

    distinct_values = list(
        dict.fromkeys(
            str(candidate.value)
            for candidate in candidates
        )
    )

    if len(distinct_values) > 1:
        warnings.append(
            (
                f"Conflicting values found for "
                f"{field_name}: "
                f"{', '.join(distinct_values)}. "
                f"Selected "
                f"{selected_candidate.value} "
                f"from page "
                f"{selected_candidate.page_number}."
            )
        )

    if (
        selected_candidate
        .confidence_score
        < minimum_confidence
    ):
        warnings.append(
            (
                f"Low-confidence extraction for "
                f"{field_name}: "
                f"{selected_candidate.confidence_score:.2f}."
            )
        )

    return ExtractedPolicyField(
        name=field_name,
        value=selected_candidate.value,
        raw_value=(
            selected_candidate.raw_value
        ),
        found=True,
        page_number=(
            selected_candidate.page_number
        ),
        source_text=(
            selected_candidate.source_text
        ),
        confidence_score=(
            selected_candidate
            .confidence_score
        ),
        extraction_method=(
            selected_candidate
            .extraction_method
        ),
    )


def extract_policy_fields(
    pages: Iterable[PolicySourcePage],
    *,
    minimum_confidence: float = 0.75,
) -> PolicyDocumentExtraction:
    """
    Extract and normalize policy fields from document pages.

    The function is deterministic and does not call an external model.
    It preserves page evidence and emits warnings for conflicts,
    invalid values, low-confidence OCR, and missing required fields.
    """

    if not (
        0
        <= minimum_confidence
        <= 1
    ):
        raise ValueError(
            "minimum_confidence must be "
            "between 0 and 1."
        )

    ordered_pages = sorted(
        list(pages),
        key=lambda page:
            page.page_number,
    )

    warnings: list[str] = []

    candidates_by_field: dict[
        str,
        list[_FieldCandidate],
    ] = {
        rule.name: []
        for rule in _FIELD_RULES
    }

    for page in ordered_pages:
        for rule in _FIELD_RULES:
            candidates_by_field[
                rule.name
            ].extend(
                _extract_labeled_candidates(
                    page,
                    rule,
                    warnings,
                )
            )

        if not candidates_by_field[
            "policy_number"
        ]:
            fallback_candidate = (
                _extract_policy_number_fallback(
                    page
                )
            )

            if fallback_candidate:
                candidates_by_field[
                    "policy_number"
                ].append(
                    fallback_candidate
                )

    extracted_fields: dict[
        str,
        ExtractedPolicyField,
    ] = {}

    for rule in _FIELD_RULES:
        extracted_field = (
            _select_candidate(
                field_name=rule.name,
                candidates=(
                    candidates_by_field[
                        rule.name
                    ]
                ),
                warnings=warnings,
                minimum_confidence=(
                    minimum_confidence
                ),
            )
        )

        extracted_fields[
            rule.name
        ] = extracted_field

        if (
            rule.required
            and not extracted_field.found
        ):
            warnings.append(
                (
                    f"Required field "
                    f"{rule.name} "
                    f"was not found."
                )
            )

    found_confidences = [
        field.confidence_score
        for field in (
            extracted_fields.values()
        )
        if (
            field.found
            and field.confidence_score
            is not None
        )
    ]

    document_confidence = (
        round(
            sum(found_confidences)
            / len(found_confidences),
            4,
        )
        if found_confidences
        else 0.0
    )

    return PolicyDocumentExtraction(
        fields=extracted_fields,
        warnings=tuple(
            dict.fromkeys(
                warnings
            )
        ),
        document_confidence=(
            document_confidence
        ),
        page_count=len(
            ordered_pages
        ),
    )


def get_policy_field_names() -> tuple[
    str,
    ...,
]:
    return tuple(
        _FIELD_RULES_BY_NAME.keys()
    )