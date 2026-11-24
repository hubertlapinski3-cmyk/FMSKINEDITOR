"""UiDocument (Gate B): an additive, read-only adapter over the existing render outputs. See model.py and docs/UIDOCUMENT-GATEB.md."""
from .build import Builder, Source, build_document, compare_documents, structural_keys
from .model import SCHEMA, Edge, Gap, Graph, UiDocument, UiNode

__all__ = ["Builder", "Source", "build_document", "compare_documents", "structural_keys", "SCHEMA", "Edge", "Gap", "Graph", "UiDocument", "UiNode"]
