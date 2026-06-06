"""Adapters between external index formats and :class:`semantic_merge.SemanticIndex`.

Adapters import heavy/optional third-party libraries (pandas, pyarrow) lazily,
inside their functions, so the core package stays dependency-free. Install the
extra with ``pip install -e ".[graphrag]"``.
"""
