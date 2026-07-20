"""Thin Python wrappers over the Rust CST core."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Sequence

from plintus import _core

if TYPE_CHECKING:
    from plintus._core import PyDocument


@dataclass(frozen=True)
class Node:
    doc: "Document"
    id: int
    kind: str
    start: int
    end: int
    line: int
    col: int
    parent_id: int | None
    _text: str | None = None

    def text(self) -> str:
        if self._text is not None:
            return self._text
        return self.doc._py.node_text(self.id)


class Document:
    """Wrapper over the Rust `PyDocument`.

    The underlying CST is freed when this object is garbage-collected (or when
    `close()` / context-manager exit is called). Use as a context manager when
    you want deterministic cleanup:

        with parse_file(path, source)[0] as doc:
            ...
    """

    def __init__(self, py: "PyDocument") -> None:
        self._py = py
        self.path: str = py.path
        self.source: str = py.source
        self.node_count: int = py.node_count

    def close(self) -> None:
        # Drop the reference to the Rust document so it can be freed eagerly.
        # Idempotent.
        py = getattr(self, "_py", None)
        if py is not None:
            self._py = None
            # `py` goes out of scope here; PyO3 refcount drop frees the Arc<Document>.

    def __enter__(self) -> "Document":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def __del__(self) -> None:
        self.close()

    def select(self, kinds: Sequence[str] = ()) -> list[Node]:
        ids = self._py.select(list(kinds))
        return self.nodes_from_ids(ids)

    def select_all(self) -> list[Node]:
        return self.nodes_from_ids(self._py.all_nodes())

    def nodes_from_ids(self, ids: Sequence[int]) -> list[Node]:
        batch = self._py.nodes_batch(list(ids))
        out: list[Node] = []
        for item in batch:
            out.append(
                Node(
                    doc=self,
                    id=int(item["id"]),
                    kind=str(item["kind"]),
                    start=int(item["start"]),
                    end=int(item["end"]),
                    line=int(item["line"]),
                    col=int(item["col"]),
                    parent_id=item["parent"],
                    _text=str(item["text"]),
                )
            )
        return out

    def parent(self, node_id: int) -> Node | None:
        pid = self._py.node_parent(node_id)
        if pid is None:
            return None
        return self.nodes_from_ids([pid])[0]

    def children(self, node_id: int) -> list[Node]:
        ids = self._py.node_children(node_id)
        return self.nodes_from_ids(ids)

    def ancestors(self, node_id: int) -> list[Node]:
        ids = self._py.node_ancestors(node_id)
        return self.nodes_from_ids(ids)


def parse_file(path: str, source: str | None = None) -> tuple[Document, int]:
    if source is None:
        with open(path, encoding="utf-8") as f:
            source = f.read()
    py_doc, micros = _core.parse_file(path, source)
    return Document(py_doc), int(micros)


def discover(paths: Sequence[str]) -> list[str]:
    return list(_core.discover(list(paths)))


def rust_api_version() -> str:
    return str(_core.api_version())
