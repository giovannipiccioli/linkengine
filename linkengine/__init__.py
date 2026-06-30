"""
linkengine — a pure-Python engine that recognizes, parses and normalizes Italian legal
citations into stable identifiers (URN-NIR / ECLI / CELEX / PRAX).

Design: the input text is kept immutable and the engine accumulates a typed **span set** over
it (character offsets are first-class — ideal for anchoring), then assembles spans into
references and builds each reference's canonical identifier directly from its fields.

Public API::

    from linkengine import (DocumentContext, LinkEngine, generate_prax_urn, urn_to_text,
                            annotate_html)

    eng = LinkEngine()
    result = eng.extract("art. 43 del d.P.R. n. 600 del 1973", debug=True)
    for row in result.rows:        # one feature dict per recognized reference (incl. `urn`)
        print(row["text"], row["urn"])
    result.trace                   # per-recognizer spans (debug=True)

    urn_to_text("ECLI:IT:CASS:2020:1234CIV")     # -> "Cassazione civile n. 1234/2020"
    generate_prax_urn("Min. Finanze", "risoluzione", "1982-08-03", "271112")
    # -> "PRAX:MEF:RIS:1982:271112"
    annotate_html(text)                           # -> the text with citations highlighted (HTML)
    annotate_html(text, page=True)                # -> a complete standalone HTML document

``runner.run_linkengine_string(text)`` returns a pipe-separated CSV view of the rows.
"""
from .context import DocumentContext
from .engine import LinkEngine
from .model import Entity, Span, Reference, ExtractResult
from .urn import generate_prax_urn, urn_to_text
from .html import annotate_html

__all__ = ["LinkEngine", "DocumentContext", "Entity", "Span", "Reference", "ExtractResult",
           "generate_prax_urn", "urn_to_text", "annotate_html"]
