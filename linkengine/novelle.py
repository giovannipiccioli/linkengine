"""Conservative scope detection for amendments in ``normativa`` mode.

This is deliberately not a legislative-amendment parser.  It performs one small job: decide
whether an otherwise bare partition belongs to the unit being read, to one confidently named
amended act, or to neither.  Ordinary citation recognition remains authoritative and complete
external citations are never rebuilt here.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Dict, List, Optional, Sequence, Tuple

from .model import Entity, PARTITION_RANK, Reference, Span
from .normalize import partition_to_locator
from .normativa import ATTACHED_ATTR, CURRENT_ATTR, INTERNAL_ATTR


_TOP_LEVEL = re.compile(r"^\s*\d+(?:-[a-z]+)?\.\s+", re.I | re.M)
_AMENDMENT = re.compile(
    r"\b(?:sono\s+apportat[ei]\s+(?:le\s+)?seguenti\s+modificazioni|"
    r"seguenti\s+modificazioni|"
    r"(?:è|e'|sono)\s+(?:inserit[oaie]|aggiunt[oaie]|sostituit[oaie]|"
    r"abrogat[oaie]|soppress[oaie]|modificat[oaie]))\b",
    re.I,
)
_HAS_DISPOSED = re.compile(r"\bha\s+disposto\b", re.I)
_CLAUSE_CUT = re.compile(r";|\.\s+(?=[A-ZÀ-Ü])|\n\s*\n")
_ARTICLE_HEADING = re.compile(
    r"^\s*(?:art(?:icolo)?\.\s*)?(\d+(?:[-\s]?(?:bis|ter|quater|quinquies|"
    r"sexies|septies|octies|novies|decies))?)\s*(?:\([^)]{0,100}\))?\s*"
    r"(?:[.:–—-]\s*)?",
    re.I,
)
_COMMA_HEADING = re.compile(
    r"^\s*(\d+(?:[-\s]?(?:bis|ter|quater|quinquies|sexies|septies|octies|"
    r"novies|decies))?)\.\s+",
    re.I,
)

_IDENTITY_FIELDS = (
    "ref-type", "ref-scope", "alias", "doc-type", "authority", "ministry", "region",
    "other-authority", "eu-acronym", "number", "year", "full-number", "doc-date",
)


@dataclass(frozen=True)
class Quote:
    start: int
    inner_start: int
    inner_end: int
    end: int

    def contains(self, position: int) -> bool:
        return self.inner_start <= position < self.inner_end


@dataclass(frozen=True)
class ActMention:
    start: int
    end: int
    act_base: str
    row: Dict[str, str]


@dataclass(frozen=True)
class AmendmentFrame:
    start: int
    end: int
    target: ActMention

    def contains(self, position: int) -> bool:
        return self.start <= position < self.end


@dataclass(frozen=True)
class ScopeTarget:
    """A target act for one partition-only reference; ``None`` means the current unit."""

    act_base: Optional[str]
    locator: str = ""
    row: Optional[Dict[str, str]] = None

    @property
    def is_current(self) -> bool:
        return self.act_base is None


def seed_row_from_target(row: Dict[str, str], target: Dict[str, str]) -> None:
    """Copy only act-identity fields, preserving the candidate's text and partition."""
    for field in _IDENTITY_FIELDS:
        row[field] = target.get(field, "")


def _quote_spans(text: str) -> List[Quote]:
    """Return balanced Italian/typographic/straight quote intervals in source order."""
    pairs = {"«": "»", "“": "”", "„": "”"}
    stack: List[Tuple[int, str]] = []
    found: List[Quote] = []
    for pos, char in enumerate(text):
        if stack and char == stack[-1][1]:
            start, _close = stack.pop()
            found.append(Quote(start, start + 1, pos, pos + 1))
            continue
        if char == '"':
            if stack and stack[-1][1] == '"':
                start, _close = stack.pop()
                found.append(Quote(start, start + 1, pos, pos + 1))
            else:
                stack.append((pos, '"'))
            continue
        if char in pairs:
            stack.append((pos, pairs[char]))
    return sorted(found, key=lambda quote: (quote.start, quote.end))


class NovellaScopes:
    """Classify normativa-only candidates without modifying ordinary references."""

    def __init__(self, text: str, spans: Sequence[Span], references: Sequence[Reference],
                 rows: Sequence[Dict[str, str]]):
        self.text = text
        self.spans = list(spans)
        self.quotes = _quote_spans(text)
        self.mentions = self._act_mentions(references, rows)
        self.block_starts = self._block_starts()
        self.frames = self._amendment_frames()

    def _quote_at(self, position: int) -> Optional[Quote]:
        return next((quote for quote in self.quotes if quote.contains(position)), None)

    def _outside_quotes(self, position: int) -> bool:
        return self._quote_at(position) is None

    def _act_mentions(self, references: Sequence[Reference],
                      rows: Sequence[Dict[str, str]]) -> List[ActMention]:
        mentions = {}
        for ref, row in zip(references, rows):
            if ref.attrs.get(INTERNAL_ATTR) or row.get("ref-type") != "legislation":
                continue
            urn = row.get("urn", "")
            if not (urn.startswith("urn:nir:") or urn.upper().startswith("CELEX:")):
                continue
            act_base = urn.split("~", 1)[0]
            identity = [span for span in ref.spans if span.entity not in PARTITION_RANK]
            if not identity:
                continue
            start = min(span.start for span in identity)
            end = max(span.end for span in identity)
            mentions[(start, end, act_base)] = ActMention(start, end, act_base, row)
        return sorted(mentions.values(), key=lambda mention: (mention.start, mention.end))

    def _block_starts(self) -> List[int]:
        starts = [0]
        starts.extend(match.start() for match in _TOP_LEVEL.finditer(self.text)
                      if self._outside_quotes(match.start()))
        return sorted(set(starts))

    def _block(self, position: int) -> Tuple[int, int]:
        start = max(value for value in self.block_starts if value <= position)
        later = [value for value in self.block_starts if value > position]
        return start, (later[0] if later else len(self.text))

    def _clause_start(self, block_start: int, position: int) -> int:
        cuts = list(_CLAUSE_CUT.finditer(self.text, block_start, position))
        return cuts[-1].end() if cuts else block_start

    def _amendment_frames(self) -> List[AmendmentFrame]:
        """Pair amendment verbs with a nearby preceding complete act.

        The first such pair governs the surrounding numbered paragraph; later pairs in that
        paragraph start a new clause-local frame.  Triggers and apparent paragraph numbers
        inside quotes are ignored.
        """
        pairs = []
        for match in _AMENDMENT.finditer(self.text):
            if not self._outside_quotes(match.start()):
                continue
            block_start, block_end = self._block(match.start())
            eligible = [mention for mention in self.mentions
                        if block_start <= mention.start and mention.end <= match.start()
                        and self._outside_quotes(mention.start)
                        and match.start() - mention.end <= 280]
            if not eligible:
                continue
            substantive = [mention for mention in eligible
                           if not re.search(
                               r"\bconvertit[oa]\b.{0,65}\bdalla\s+$",
                               self.text[max(block_start, mention.start - 100):mention.start],
                               re.I | re.S,
                           )]
            target = max(substantive or eligible, key=lambda mention: mention.end)
            pairs.append((match.start(), block_start, block_end, target))

        frames: List[AmendmentFrame] = []
        for block in sorted({(start, end) for _, start, end, _ in pairs}):
            start, end = block
            local = [(trigger, target) for trigger, bs, be, target in pairs
                     if bs == start and be == end]
            local.sort(key=lambda pair: pair[0])
            changes = []
            for trigger, target in local:
                if changes and changes[-1][1].act_base == target.act_base:
                    continue
                frame_start = start if not changes else self._clause_start(start, target.start)
                changes.append((frame_start, target))
            for index, (frame_start, target) in enumerate(changes):
                frame_end = changes[index + 1][0] if index + 1 < len(changes) else end
                frames.append(AmendmentFrame(frame_start, frame_end, target))
        return sorted(frames, key=lambda frame: (frame.start, frame.end))

    def _frame_at(self, position: int) -> Optional[AmendmentFrame]:
        matches = [frame for frame in self.frames if frame.contains(position)]
        return max(matches, key=lambda frame: frame.start) if matches else None

    def _note_target(self, position: int) -> Optional[Tuple[ActMention, str]]:
        """Resolve the narrow editorial grammar ``X ha disposto (con l'art. Y)``."""
        for match in _HAS_DISPOSED.finditer(self.text):
            if not self._outside_quotes(match.start()):
                continue
            local_start = max(0, self.text.rfind("\n\n", max(0, match.start() - 1200),
                                                match.start()) + 2)
            actors = [mention for mention in self.mentions
                      if local_start <= mention.start and mention.end <= match.start()
                      and self._outside_quotes(mention.start)]
            if not actors:
                continue
            actor = min(actors, key=lambda mention: mention.start)
            following_quote = next((quote for quote in self.quotes
                                    if match.end() <= quote.start <= match.end() + 600), None)
            note_end = following_quote.end if following_quote else min(
                len(self.text), match.end() + 350)
            if not (match.end() <= position < note_end):
                continue
            if following_quote and following_quote.contains(position):
                quoted = {mention.act_base: mention for mention in self.mentions
                          if following_quote.contains(mention.start)}
                if len(quoted) == 1:
                    return next(iter(quoted.values())), ""
            parenthetical_end = following_quote.start if following_quote else note_end
            articles = [span for span in self.spans
                        if span.entity == Entity.ARTICLE
                        and match.end() <= span.start < parenthetical_end]
            locator = partition_to_locator(
                f"articolo-{articles[-1].value}") if articles else ""
            return actor, locator
        return None

    def _looks_like_amendment(self, ref: Reference) -> bool:
        block_start, block_end = self._block(ref.start)
        left = max(block_start, ref.start - 240)
        right = min(block_end, ref.end + 300)
        return any(self._outside_quotes(match.start())
                   for match in _AMENDMENT.finditer(self.text, left, right))

    def _is_quote_heading(self, ref: Reference, quote: Quote) -> bool:
        article = next((span for span in ref.spans if span.entity == Entity.ARTICLE), None)
        if article is None or self.text[quote.inner_start:article.start].strip():
            return False
        prefix = self.text[quote.inner_start:min(quote.inner_end, article.end + 120)]
        match = _ARTICLE_HEADING.match(prefix)
        return bool(match and match.end() > article.end - quote.inner_start)

    def _local_locator(self, ref: Reference, frame: AmendmentFrame) -> str:
        """Find only the article/comma needed to resolve a bare subordinate partition."""
        quote = self._quote_at(ref.start)
        limit = quote.start if quote else ref.start
        articles = [span for span in self.spans
                    if span.entity == Entity.ARTICLE and frame.start <= span.start < limit
                    and self._outside_quotes(span.start)
                    and not span.attrs.get("normativa-relative")]
        article = max(articles, key=lambda span: span.start) if articles else None
        commas = [span for span in self.spans
                  if span.entity == Entity.COMMA and frame.start <= span.start < limit
                  and self._outside_quotes(span.start)
                  and not span.attrs.get("normativa-relative")
                  and (article is None or span.start > article.start)]
        comma = max(commas, key=lambda span: span.start) if commas else None

        if quote:
            opening = self.text[quote.inner_start:min(quote.inner_end, quote.inner_start + 180)]
            heading = _ARTICLE_HEADING.match(opening)
            explicit_article = bool(re.match(r"^\s*art", opening, re.I))
            suffixed_article = bool(heading and "-" in heading.group(1))
            rubric_article = bool(heading and "(" in opening[:heading.end() + 2])
            if heading and (explicit_article or suffixed_article or rubric_article):
                article = Span(quote.inner_start, quote.inner_start + heading.end(),
                               Entity.ARTICLE, heading.group(1))
                tail = opening[heading.end():]
                comma_heading = _COMMA_HEADING.match(tail.lstrip(" .:–—-"))
                comma = (Span(quote.inner_start, quote.inner_start, Entity.COMMA,
                              comma_heading.group(1)) if comma_heading else None)
            else:
                comma_heading = _COMMA_HEADING.match(opening)
                if comma_heading and article is not None:
                    comma = Span(quote.inner_start, quote.inner_start, Entity.COMMA,
                                 comma_heading.group(1))

        pieces = []
        if article is not None:
            pieces.append(f"articolo-{article.value}")
        if comma is not None:
            pieces.append(f"comma-{comma.value}")
        return partition_to_locator("_".join(pieces)) if pieces else ""

    def target_for(self, ref: Reference) -> Optional[ScopeTarget]:
        """Return current/target scope, or ``None`` when guessing would be unsafe."""
        if ref.attrs.get(CURRENT_ATTR):
            return ScopeTarget(None)

        quote = self._quote_at(ref.start)
        if quote and self._is_quote_heading(ref, quote):
            return None

        note_target = self._note_target(ref.start)
        if note_target is not None:
            mention, locator = note_target
            return ScopeTarget(mention.act_base, locator, mention.row)

        frame = self._frame_at(ref.start)
        if frame is not None:
            return ScopeTarget(
                frame.target.act_base,
                self._local_locator(ref, frame),
                frame.target.row,
            )

        if ref.attrs.get(ATTACHED_ATTR) or self._looks_like_amendment(ref):
            return None
        return ScopeTarget(None)
