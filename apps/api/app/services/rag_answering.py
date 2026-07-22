from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Sequence
from uuid import UUID

from sqlalchemy.orm import Session

from apps.api.app.core.config import settings
from apps.api.app.services.rag_embeddings import (
    DenseEmbeddingModel,
)
from apps.api.app.services.rag_retrieval import (
    RAGSearchHit,
    RAGSearchResult,
    normalize_rag_query,
    search_document_chunks,
)


DEFAULT_MAX_CITATIONS = 4
MAX_ALLOWED_CITATIONS = 10
MAX_CITATION_EXCERPT_CHARACTERS = 600

TOKEN_PATTERN = re.compile(
    r"[A-Za-z0-9][A-Za-z0-9_-]*"
)

SENTENCE_SPLIT_PATTERN = re.compile(
    r"(?<=[.!?])\s+|\n+"
)

STOP_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "by",
    "for",
    "from",
    "has",
    "have",
    "how",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "their",
    "this",
    "to",
    "was",
    "were",
    "what",
    "when",
    "where",
    "which",
    "who",
    "why",
    "with",
}


class RAGAnsweringError(RuntimeError):
    """Base exception for grounded answer generation."""


class InvalidRAGAnswerRequestError(
    RAGAnsweringError,
    ValueError,
):
    """Raised when an answer-generation request is invalid."""


@dataclass(frozen=True)
class StructuredFieldDefinition:
    """Configuration for one structured OCR field."""

    key: str
    label: str
    question_aliases: tuple[str, ...]
    answer_template: str
    patterns: tuple[str, ...]
    prefer_last_match: bool = False


@dataclass(frozen=True)
class StructuredFieldMatch:
    """A structured value extracted from OCR content."""

    field_key: str
    field_label: str
    value: str
    excerpt: str
    answer_statement: str


@dataclass(frozen=True)
class RAGCitation:
    """One numbered citation attached to a grounded answer."""

    citation_number: int

    chunk_id: UUID
    workspace_id: UUID
    document_id: UUID
    document_name: str
    processing_run_id: UUID
    document_page_id: UUID

    chunk_index: int
    page_number: int

    start_character: int
    end_character: int

    excerpt: str
    similarity_score: float
    cosine_distance: float

    extra_metadata: dict[str, Any] = field(
        default_factory=dict,
    )


@dataclass(frozen=True)
class GroundedRAGAnswer:
    """Grounded answer and all supporting source references."""

    question: str
    answer: str

    is_grounded: bool
    confidence_score: float

    retrieved_chunk_count: int
    citation_count: int

    embedding_provider: str
    embedding_model: str
    embedding_dimensions: int

    citations: list[RAGCitation]


STRUCTURED_FIELD_DEFINITIONS: tuple[
    StructuredFieldDefinition,
    ...,
] = (
    StructuredFieldDefinition(
        key="total_net_payable",
        label="Total Net Payable",
        question_aliases=(
            "total net payable",
            "net payable",
            "net salary",
            "take home salary",
            "take home pay",
            "final salary",
        ),
        answer_template=(
            "The total net payable is {value}."
        ),
        patterns=(
            (
                r"\btotal\s+net\s+payable\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[₹$€£¥]?\s*"
                r"\(?-?\s*"
                r"\d(?:[\d,]*\d)?"
                r"(?:\.\d{1,2})?"
                r"\)?)"
            ),
            (
                r"\bnet\s+payable\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[₹$€£¥]?\s*"
                r"\(?-?\s*"
                r"\d(?:[\d,]*\d)?"
                r"(?:\.\d{1,2})?"
                r"\)?)"
            ),
        ),
        prefer_last_match=True,
    ),
    StructuredFieldDefinition(
        key="gross_earnings",
        label="Gross Earnings",
        question_aliases=(
            "gross earnings",
            "gross salary",
            "gross pay",
            "total earnings",
        ),
        answer_template=(
            "The gross earnings are {value}."
        ),
        patterns=(
            (
                r"\bgross\s+earnings\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[₹$€£¥]?\s*"
                r"\(?-?\s*"
                r"\d(?:[\d,]*\d)?"
                r"(?:\.\d{1,2})?"
                r"\)?)"
            ),
            (
                r"\bgross\s+(?:salary|pay)\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[₹$€£¥]?\s*"
                r"\(?-?\s*"
                r"\d(?:[\d,]*\d)?"
                r"(?:\.\d{1,2})?"
                r"\)?)"
            ),
        ),
        prefer_last_match=True,
    ),
    StructuredFieldDefinition(
        key="total_deductions",
        label="Total Deductions",
        question_aliases=(
            "total deductions",
            "deductions",
            "deduction amount",
        ),
        answer_template=(
            "The total deductions are {value}."
        ),
        patterns=(
            (
                r"\btotal\s+deductions?\b"
                r"\s*(?:\(\s*-\s*\))?"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[₹$€£¥]?\s*"
                r"\(?-?\s*"
                r"\d(?:[\d,]*\d)?"
                r"(?:\.\d{1,2})?"
                r"\)?)"
            ),
        ),
        prefer_last_match=True,
    ),
    StructuredFieldDefinition(
        key="pay_period",
        label="Pay Period",
        question_aliases=(
            "pay period",
            "salary period",
            "payroll period",
            "salary month",
            "month of salary",
            "payslip month",
        ),
        answer_template=(
            "The pay period is {value}."
        ),
        patterns=(
            (
                r"\bpay\s*period\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[A-Za-z]{3,9}\s+\d{4}"
                r")"
            ),
            (
                r"\bpayroll\s*period\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[A-Za-z]{3,9}\s+\d{4}"
                r")"
            ),
            (
                r"\bpayslip\s+for\s+the\s+month\s+of\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[A-Za-z]{3,9}\s+\d{4}"
                r")"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="pay_date",
        label="Pay Date",
        question_aliases=(
            "pay date",
            "payment date",
            "salary payment date",
            "salary date",
        ),
        answer_template=(
            "The pay date is {value}."
        ),
        patterns=(
            (
                r"\bpay\s*date\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
                r")"
            ),
            (
                r"\bpayment\s*date\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
                r")"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="employee_name",
        label="Employee Name",
        question_aliases=(
            "employee name",
            "name of employee",
            "who is the employee",
            "whose payslip",
        ),
        answer_template=(
            "The employee name is {value}."
        ),
        patterns=(
            (
                r"\bemployee\s*name\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[A-Za-z]"
                r"[A-Za-z .'-]{1,80}?"
                r")"
                r"(?=\s*(?:"
                r",\s*\d"
                r"|employee\s+net\s+pay"
                r"|employee\s+id"
                r"|designation\b"
                r"|date\s+of\s+joining\b"
                r"|pay\s+period\b"
                r"|paid\s+days\b"
                r"|lop\s+days\b"
                r"|pay\s+date\b"
                r"|$"
                r"))"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="employee_id",
        label="Employee ID",
        question_aliases=(
            "employee id",
            "employee number",
            "employee code",
            "staff id",
        ),
        answer_template=(
            "The employee ID is {value}."
        ),
        patterns=(
            (
                r"\bemployee\s*(?:id|number|code|no\.?)\b"
                r"\s*[:#\-]?\s*"
                r"(?P<value>"
                r"[A-Za-z0-9][A-Za-z0-9/_-]{2,}"
                r")"
            ),
            (
                r"\bemployee\s*name\b"
                r"\s*[:\-]?\s*"
                r"[A-Za-z][A-Za-z .'-]{1,80}?"
                r",\s*"
                r"(?P<value>\d{3,})"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="designation",
        label="Designation",
        question_aliases=(
            "designation",
            "job title",
            "employee role",
            "position",
        ),
        answer_template=(
            "The employee designation is {value}."
        ),
        patterns=(
            (
                r"\bdesignation\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[A-Za-z]"
                r"[A-Za-z0-9 &'./()-]{1,100}?"
                r")"
                r"(?=\s*(?:"
                r"#\s*\d"
                r"|date\s+of\s+joining\b"
                r"|pay\s+period\b"
                r"|paid\s+days\b"
                r"|lop\s+days\b"
                r"|pay\s+date\b"
                r"|employee\s+id\b"
                r"|$"
                r"))"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="date_of_joining",
        label="Date of Joining",
        question_aliases=(
            "date of joining",
            "joining date",
            "employment start date",
            "employee start date",
        ),
        answer_template=(
            "The date of joining is {value}."
        ),
        patterns=(
            (
                r"\bdate\s+of\s+joining\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
                r")"
            ),
            (
                r"\bjoining\s+date\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
                r")"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="paid_days",
        label="Paid Days",
        question_aliases=(
            "paid days",
            "number of paid days",
            "days paid",
        ),
        answer_template=(
            "The number of paid days is {value}."
        ),
        patterns=(
            (
                r"\bpaid\s+days\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>\d+(?:\.\d+)?)"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="lop_days",
        label="LOP Days",
        question_aliases=(
            "lop days",
            "loss of pay days",
            "unpaid days",
        ),
        answer_template=(
            "The number of LOP days is {value}."
        ),
        patterns=(
            (
                r"\blop\s+days\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>\d+(?:\.\d+)?)"
            ),
            (
                r"\bloss\s+of\s+pay\s+days\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>\d+(?:\.\d+)?)"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="policy_number",
        label="Policy Number",
        question_aliases=(
            "policy number",
            "policy no",
            "policy id",
            "insurance policy number",
        ),
        answer_template=(
            "The policy number is {value}."
        ),
        patterns=(
            (
                r"\bpolicy\s*(?:number|no\.?|id)\b"
                r"\s*[:#\-]?\s*"
                r"(?P<value>"
                r"[A-Za-z0-9]"
                r"[A-Za-z0-9/_-]{2,}"
                r")"
            ),
        ),
    ),
    StructuredFieldDefinition(
        key="customer_name",
        label="Customer Name",
        question_aliases=(
            "customer name",
            "name of customer",
            "which customer",
            "who is the customer",
        ),
        answer_template=(
            "The customer name is {value}."
        ),
        patterns=(
            (
                r"\bcustomer(?:\s+name)?\b"
                r"\s*[:\-]?\s*"
                r"(?P<value>"
                r"[A-Za-z]"
                r"[A-Za-z .'-]{1,80}?"
                r")"
                r"(?=\s*(?:"
                r"policy\b"
                r"|policy\s+number\b"
                r"|customer\s+id\b"
                r"|date\b"
                r"|$"
                r"))"
            ),
        ),
    ),
)


STRUCTURED_FIELD_BY_KEY = {
    definition.key: definition
    for definition in STRUCTURED_FIELD_DEFINITIONS
}


def normalize_answer_question(
    question: str,
) -> str:
    """Normalize and validate a RAG answer question."""

    try:
        return normalize_rag_query(
            question
        )
    except ValueError as error:
        raise InvalidRAGAnswerRequestError(
            str(error)
        ) from error


def resolve_max_citations(
    max_citations: int | None,
) -> int:
    """Resolve and validate the citation limit."""

    resolved_max_citations = (
        max_citations
        if max_citations is not None
        else DEFAULT_MAX_CITATIONS
    )

    if resolved_max_citations < 1:
        raise InvalidRAGAnswerRequestError(
            "max_citations must be greater than "
            "or equal to one."
        )

    if (
        resolved_max_citations
        > MAX_ALLOWED_CITATIONS
    ):
        raise InvalidRAGAnswerRequestError(
            "max_citations cannot exceed "
            f"{MAX_ALLOWED_CITATIONS}."
        )

    return resolved_max_citations


def tokenize_answer_text(
    text: str,
) -> set[str]:
    """Return meaningful lowercase tokens for sentence scoring."""

    tokens = {
        token.lower()
        for token in TOKEN_PATTERN.findall(
            text
        )
    }

    return {
        token
        for token in tokens
        if token not in STOP_WORDS
        and len(token) > 1
    }


def normalize_matching_text(
    text: str,
) -> str:
    """Normalize text for phrase and alias matching."""

    return re.sub(
        r"[^a-z0-9]+",
        " ",
        text.casefold(),
    ).strip()


def phrase_exists(
    *,
    phrase: str,
    normalized_text: str,
) -> bool:
    """Check whether a normalized phrase exists as words."""

    normalized_phrase = normalize_matching_text(
        phrase
    )

    if not normalized_phrase:
        return False

    return (
        f" {normalized_phrase} "
        in f" {normalized_text} "
    )


def identify_requested_structured_field(
    question: str,
) -> StructuredFieldDefinition | None:
    """Identify the structured field requested by the question."""

    normalized_question = normalize_matching_text(
        question
    )

    for definition in STRUCTURED_FIELD_DEFINITIONS:
        if any(
            phrase_exists(
                phrase=alias,
                normalized_text=normalized_question,
            )
            for alias in definition.question_aliases
        ):
            return definition

    return None


def normalize_ocr_text(
    text_content: str,
) -> str:
    """Normalize OCR content while retaining its words and values."""

    return " ".join(
        text_content.replace(
            "\r",
            "\n",
        ).split()
    ).strip()


def clean_structured_field_value(
    value: str,
) -> str:
    """Clean punctuation and spacing around an OCR field value."""

    cleaned_value = " ".join(
        value.split()
    ).strip()

    cleaned_value = cleaned_value.strip(
        " \t\r\n,;:|"
    )

    cleaned_value = re.sub(
        r"\s+([,./])",
        r"\1",
        cleaned_value,
    )

    cleaned_value = re.sub(
        r"([,./])\s+",
        r"\1",
        cleaned_value,
    )

    cleaned_value = re.sub(
        r"\(\s+",
        "(",
        cleaned_value,
    )

    cleaned_value = re.sub(
        r"\s+\)",
        ")",
        cleaned_value,
    )

    return cleaned_value


def extract_definition_value(
    *,
    definition: StructuredFieldDefinition,
    text_content: str,
) -> str | None:
    """Extract one configured field from OCR text."""

    normalized_text = normalize_ocr_text(
        text_content
    )

    if not normalized_text:
        return None

    matching_results: list[
        re.Match[str]
    ] = []

    for pattern in definition.patterns:
        matching_results.extend(
            re.finditer(
                pattern,
                normalized_text,
                flags=re.IGNORECASE,
            )
        )

    if not matching_results:
        return None

    selected_match = (
        matching_results[-1]
        if definition.prefer_last_match
        else matching_results[0]
    )

    raw_value = selected_match.group(
        "value"
    )

    cleaned_value = (
        clean_structured_field_value(
            raw_value
        )
    )

    if not cleaned_value:
        return None

    return cleaned_value


def split_answer_sentences(
    text_content: str,
) -> list[str]:
    """Split chunk text into normalized candidate sentences."""

    normalized_newlines = (
        text_content.replace(
            "\r\n",
            "\n",
        ).replace(
            "\r",
            "\n",
        )
    )

    candidate_sentences = [
        " ".join(
            sentence.split()
        ).strip()
        for sentence
        in SENTENCE_SPLIT_PATTERN.split(
            normalized_newlines
        )
        if sentence.strip()
    ]

    return [
        sentence
        for sentence in candidate_sentences
        if sentence
    ]


def find_sentence_containing_value(
    *,
    text_content: str,
    value: str,
    maximum_characters: int = 240,
) -> str | None:
    """Find a concise source sentence containing a field value."""

    normalized_value = value.casefold()

    for sentence in split_answer_sentences(
        text_content
    ):
        if (
            normalized_value
            not in sentence.casefold()
        ):
            continue

        if len(sentence) > maximum_characters:
            continue

        return sentence

    return None


def build_structured_field_excerpt(
    *,
    definition: StructuredFieldDefinition,
    value: str,
    question: str,
    text_content: str,
) -> str:
    """Build concise citation evidence for a structured value."""

    if definition.key == "policy_number":
        customer_definition = (
            STRUCTURED_FIELD_BY_KEY[
                "customer_name"
            ]
        )

        customer_name = (
            extract_definition_value(
                definition=customer_definition,
                text_content=text_content,
            )
        )

        if customer_name:
            return (
                f"Customer: {customer_name}; "
                f"Policy Number: {value}"
            )

        matching_sentence = (
            find_sentence_containing_value(
                text_content=text_content,
                value=value,
            )
        )

        if matching_sentence:
            return matching_sentence

    del question

    return (
        f"{definition.label}: {value}"
    )


def extract_structured_field_match(
    *,
    question: str,
    text_content: str,
) -> StructuredFieldMatch | None:
    """Extract a requested key-value field from OCR text."""

    definition = (
        identify_requested_structured_field(
            question
        )
    )

    if definition is None:
        return None

    value = extract_definition_value(
        definition=definition,
        text_content=text_content,
    )

    if value is None:
        return None

    excerpt = build_structured_field_excerpt(
        definition=definition,
        value=value,
        question=question,
        text_content=text_content,
    )

    answer_statement = (
        definition.answer_template.format(
            value=value
        )
    )

    return StructuredFieldMatch(
        field_key=definition.key,
        field_label=definition.label,
        value=value,
        excerpt=excerpt,
        answer_statement=answer_statement,
    )


def truncate_citation_excerpt(
    text_content: str,
    *,
    maximum_characters: int = (
        MAX_CITATION_EXCERPT_CHARACTERS
    ),
) -> str:
    """Limit a citation excerpt without cutting words abruptly."""

    normalized_text = " ".join(
        text_content.split()
    ).strip()

    if len(normalized_text) <= maximum_characters:
        return normalized_text

    truncated_text = normalized_text[
        :maximum_characters
    ]

    final_space = truncated_text.rfind(
        " "
    )

    if final_space > 0:
        truncated_text = truncated_text[
            :final_space
        ]

    return (
        truncated_text.rstrip(
            " ,;:-"
        )
        + "…"
    )


def score_answer_sentence(
    *,
    sentence: str,
    question_tokens: set[str],
    similarity_score: float,
) -> float:
    """Score a sentence using token overlap and retrieval score."""

    sentence_tokens = tokenize_answer_text(
        sentence
    )

    if question_tokens:
        overlap_count = len(
            sentence_tokens.intersection(
                question_tokens
            )
        )

        overlap_score = (
            overlap_count
            / len(question_tokens)
        )
    else:
        overlap_score = 0.0

    bounded_similarity = max(
        -1.0,
        min(
            1.0,
            similarity_score,
        ),
    )

    normalized_similarity = (
        bounded_similarity + 1.0
    ) / 2.0

    return (
        overlap_score * 0.75
        + normalized_similarity * 0.25
    )


def extract_best_answer_excerpt(
    *,
    question: str,
    search_hit: RAGSearchHit,
) -> str:
    """Select concise structured evidence or the best sentence."""

    structured_match = (
        extract_structured_field_match(
            question=question,
            text_content=search_hit.text_content,
        )
    )

    if structured_match is not None:
        return truncate_citation_excerpt(
            structured_match.excerpt
        )

    question_tokens = tokenize_answer_text(
        question
    )

    sentences = split_answer_sentences(
        search_hit.text_content
    )

    if not sentences:
        return ""

    best_sentence = max(
        sentences,
        key=lambda sentence: (
            score_answer_sentence(
                sentence=sentence,
                question_tokens=question_tokens,
                similarity_score=(
                    search_hit.similarity_score
                ),
            ),
            len(
                tokenize_answer_text(
                    sentence
                )
            ),
            -len(sentence),
        ),
    )

    return truncate_citation_excerpt(
        best_sentence
    )


def build_rag_citations(
    *,
    question: str,
    search_hits: Sequence[RAGSearchHit],
    max_citations: int,
) -> list[RAGCitation]:
    """Select unique citations from retrieved chunks."""

    resolved_max_citations = (
        resolve_max_citations(
            max_citations
        )
    )

    citations: list[RAGCitation] = []
    seen_excerpts: set[str] = set()

    for search_hit in search_hits:
        structured_match = (
            extract_structured_field_match(
                question=question,
                text_content=(
                    search_hit.text_content
                ),
            )
        )

        if structured_match is not None:
            excerpt = (
                structured_match.excerpt
            )
        else:
            excerpt = (
                extract_best_answer_excerpt(
                    question=question,
                    search_hit=search_hit,
                )
            )

        excerpt = truncate_citation_excerpt(
            excerpt
        )

        if not excerpt:
            continue

        normalized_excerpt = (
            excerpt.casefold()
        )

        if normalized_excerpt in seen_excerpts:
            continue

        seen_excerpts.add(
            normalized_excerpt
        )

        citation_metadata = dict(
            search_hit.extra_metadata or {}
        )

        if structured_match is not None:
            citation_metadata.update(
                {
                    "answer_extraction": (
                        "structured_field"
                    ),
                    "answer_field_key": (
                        structured_match.field_key
                    ),
                    "answer_field_label": (
                        structured_match.field_label
                    ),
                    "answer_field_value": (
                        structured_match.value
                    ),
                    "answer_statement": (
                        structured_match.answer_statement
                    ),
                }
            )
        else:
            citation_metadata[
                "answer_extraction"
            ] = "extractive_sentence"

        citations.append(
            RAGCitation(
                citation_number=(
                    len(citations) + 1
                ),
                chunk_id=(
                    search_hit.chunk_id
                ),
                workspace_id=(
                    search_hit.workspace_id
                ),
                document_id=(
                    search_hit.document_id
                ),
                document_name=(
                    search_hit.document_name
                ),
                processing_run_id=(
                    search_hit.processing_run_id
                ),
                document_page_id=(
                    search_hit.document_page_id
                ),
                chunk_index=(
                    search_hit.chunk_index
                ),
                page_number=(
                    search_hit.page_number
                ),
                start_character=(
                    search_hit.start_character
                ),
                end_character=(
                    search_hit.end_character
                ),
                excerpt=excerpt,
                similarity_score=(
                    search_hit.similarity_score
                ),
                cosine_distance=(
                    search_hit.cosine_distance
                ),
                extra_metadata=(
                    citation_metadata
                ),
            )
        )

        if (
            len(citations)
            >= resolved_max_citations
        ):
            break

    return citations


def calculate_answer_confidence(
    citations: Sequence[RAGCitation],
) -> float:
    """Calculate a bounded confidence score from citation similarity."""

    if not citations:
        return 0.0

    average_similarity = sum(
        citation.similarity_score
        for citation in citations
    ) / len(citations)

    return round(
        max(
            0.0,
            min(
                1.0,
                average_similarity,
            ),
        ),
        6,
    )


def ensure_statement_punctuation(
    statement: str,
) -> str:
    """Ensure an answer statement ends with punctuation."""

    normalized_statement = " ".join(
        statement.split()
    ).strip()

    if not normalized_statement:
        return normalized_statement

    if normalized_statement.endswith(
        (
            ".",
            "!",
            "?",
        )
    ):
        return normalized_statement

    return normalized_statement + "."


def compose_grounded_answer(
    *,
    question: str,
    citations: Sequence[RAGCitation],
) -> str:
    """Compose a concise answer with numbered citations."""

    del question

    if not citations:
        return (
            "I could not find enough relevant information "
            "in the indexed workspace documents to answer "
            "this question."
        )

    answer_parts: list[str] = []

    for citation in citations:
        structured_statement = (
            citation.extra_metadata.get(
                "answer_statement"
            )
        )

        if (
            isinstance(
                structured_statement,
                str,
            )
            and structured_statement.strip()
        ):
            statement = structured_statement
        else:
            statement = citation.excerpt

        normalized_statement = (
            ensure_statement_punctuation(
                statement
            )
        )

        answer_parts.append(
            (
                f"{normalized_statement} "
                f"[{citation.citation_number}]"
            )
        )

    return " ".join(
        answer_parts
    )


def build_grounded_answer(
    *,
    question: str,
    search_result: RAGSearchResult,
    max_citations: int = (
        DEFAULT_MAX_CITATIONS
    ),
) -> GroundedRAGAnswer:
    """Build a grounded answer from semantic search results."""

    normalized_question = (
        normalize_answer_question(
            question
        )
    )

    citations = build_rag_citations(
        question=normalized_question,
        search_hits=search_result.items,
        max_citations=max_citations,
    )

    answer = compose_grounded_answer(
        question=normalized_question,
        citations=citations,
    )

    return GroundedRAGAnswer(
        question=normalized_question,
        answer=answer,
        is_grounded=bool(citations),
        confidence_score=(
            calculate_answer_confidence(
                citations
            )
        ),
        retrieved_chunk_count=(
            search_result.result_count
        ),
        citation_count=len(citations),
        embedding_provider=(
            search_result.embedding_provider
        ),
        embedding_model=(
            search_result.embedding_model
        ),
        embedding_dimensions=(
            search_result.embedding_dimensions
        ),
        citations=citations,
    )


def answer_document_question(
    database_session: Session,
    *,
    workspace_id: UUID,
    question: str,
    top_k: int | None = None,
    maximum_citations: int | None = None,
    minimum_similarity: float = 0.0,
    document_ids: Sequence[UUID] | None = None,
    embedding_model: (
        DenseEmbeddingModel | None
    ) = None,
) -> GroundedRAGAnswer:
    """
    Retrieve workspace chunks and construct a grounded answer.

    Structured OCR fields are extracted when possible. Other
    questions continue to use extractive sentence selection.
    """

    normalized_question = (
        normalize_answer_question(
            question
        )
    )

    resolved_max_citations = (
        resolve_max_citations(
            maximum_citations
        )
    )

    resolved_top_k = (
        top_k
        if top_k is not None
        else max(
            settings.rag_default_top_k,
            resolved_max_citations,
        )
    )

    search_result = search_document_chunks(
        database_session,
        workspace_id=workspace_id,
        query=normalized_question,
        top_k=resolved_top_k,
        minimum_similarity=minimum_similarity,
        document_ids=document_ids,
        embedding_model=embedding_model,
    )

    return build_grounded_answer(
        question=normalized_question,
        search_result=search_result,
        max_citations=(
            resolved_max_citations
        ),
    )