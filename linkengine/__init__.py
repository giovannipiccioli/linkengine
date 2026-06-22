"""
linkengine — a pure-Python engine that recognizes, parses and normalizes Italian legal
citations into stable identifiers (URN-NIR / ECLI / CELEX / PRAX).

Design: the input text is kept immutable and the engine accumulates a typed **span set** over
it (character offsets are first-class — ideal for anchoring), then assembles spans into
references and builds each reference's canonical identifier directly from its fields.

Public API::

    from linkengine import LinkEngine, urn_to_text, annotate_html

    eng = LinkEngine()
    result = eng.extract("art. 43 del d.P.R. n. 600 del 1973", debug=True)
    for row in result.rows:        # one feature dict per recognized reference (incl. `urn`)
        print(row["text"], row["urn"])
    result.trace                   # per-recognizer spans (debug=True)

    urn_to_text("ECLI:IT:CASS:2020:1234CIV")     # -> "Cassazione civile n. 1234/2020"
    annotate_html("art. 2697 c.c.")               # -> the text with the reference wrapped in a tag

``runner.run_linkengine_string(text)`` returns a pipe-separated CSV view of the rows.
"""
from .engine import LinkEngine
from .model import Entity, Span, Reference, ExtractResult
from .urn import urn_to_text
from .html import annotate_html, render_html_document

__all__ = ["LinkEngine", "Entity", "Span", "Reference", "ExtractResult",
           "urn_to_text", "annotate_html", "render_html_document"]
