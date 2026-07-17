//! Normalized CST document built from tree-sitter-python.
//!
//! `kind` is stored as `&'static str` because tree-sitter node kinds are
//! static strings — this eliminates a per-node `String` allocation with no
//! interner required. `kind_index` keys on the same `&'static str`.

use std::collections::HashMap;
use std::sync::Arc;

/// Byte span in the source (UTF-8 offsets).
#[derive(Debug, Clone, Copy, PartialEq, Eq)]
pub struct Span {
    pub start: usize,
    pub end: usize,
}

#[derive(Debug, Clone)]
pub struct NodeData {
    pub kind: &'static str,
    pub span: Span,
    pub parent: Option<u32>,
    pub children: Vec<u32>,
    pub named: bool,
}

#[derive(Debug)]
pub struct Document {
    pub path: String,
    pub source: String,
    pub nodes: Vec<NodeData>,
    pub kind_index: HashMap<&'static str, Vec<u32>>,
    pub line_starts: Vec<usize>,
}

#[derive(Debug)]
pub struct InvalidNode;

impl Document {
    pub fn node(&self, id: u32) -> Option<&NodeData> {
        self.nodes.get(id as usize)
    }

    pub fn text_of(&self, id: u32) -> Option<&str> {
        let n = self.node(id)?;
        self.source.get(n.span.start..n.span.end)
    }

    /// Returns node ids matching any of `kinds`. Empty `kinds` returns an empty
    /// vec — call `all_nodes()` explicitly to iterate the whole tree. This
    /// prevents accidental full-tree scans from rules without `targets`.
    pub fn select(&self, kinds: &[String]) -> Vec<u32> {
        if kinds.is_empty() {
            return Vec::new();
        }
        // Fast path: single kind — no sort/dedup needed.
        if kinds.len() == 1 {
            if let Some(ids) = self.kind_index.get(kinds[0].as_str()) {
                return ids.clone();
            }
            return Vec::new();
        }
        let mut out = Vec::new();
        for k in kinds {
            if let Some(ids) = self.kind_index.get(k.as_str()) {
                out.extend(ids);
            }
        }
        out.sort_unstable();
        out.dedup();
        out
    }

    /// All node ids in document order. Use sparingly.
    pub fn all_nodes(&self) -> Vec<u32> {
        (0..self.nodes.len() as u32).collect()
    }

    /// Walks parent chain from `id`. Returns `Err(InvalidNode)` if `id` is not
    /// a valid node id — callers should surface as `PyValueError` to match the
    /// other node accessors (which return `None` from `node()`).
    pub fn ancestors(&self, id: u32) -> Result<Vec<u32>, InvalidNode> {
        let mut out = Vec::new();
        let mut cur = id;
        if self.node(id).is_none() {
            return Err(InvalidNode);
        }
        while let Some(node) = self.node(cur) {
            if let Some(p) = node.parent {
                out.push(p);
                cur = p;
            } else {
                break;
            }
        }
        Ok(out)
    }

    pub fn line_col(&self, byte: usize) -> (usize, usize) {
        let line = match self.line_starts.binary_search(&byte) {
            Ok(i) => i,
            Err(i) => i.saturating_sub(1),
        };
        let col = byte.saturating_sub(self.line_starts[line]);
        (line + 1, col + 1)
    }
}

pub type SharedDocument = Arc<Document>;

/// Build line-start byte offsets. Uses `memchr` for SIMD-accelerated newline
/// scanning on large files.
pub fn build_line_starts(source: &str) -> Vec<usize> {
    let bytes = source.as_bytes();
    let mut starts = vec![0];
    for i in memchr::memchr_iter(b'\n', bytes) {
        starts.push(i + 1);
    }
    starts
}

#[cfg(test)]
mod tests {
    use super::*;

    fn empty_doc() -> Document {
        Document {
            path: String::new(),
            source: String::new(),
            nodes: Vec::new(),
            kind_index: HashMap::new(),
            line_starts: vec![0],
        }
    }

    #[test]
    fn select_empty_kinds_returns_empty() {
        let doc = empty_doc();
        assert!(doc.select(&[]).is_empty());
    }

    #[test]
    fn ancestors_invalid_id_is_err() {
        let doc = empty_doc();
        assert!(doc.ancestors(0).is_err());
    }

    #[test]
    fn line_col_basic() {
        let doc = Document {
            path: String::new(),
            source: "ab\ncd".to_string(),
            nodes: Vec::new(),
            kind_index: HashMap::new(),
            line_starts: build_line_starts("ab\ncd"),
        };
        assert_eq!(doc.line_col(0), (1, 1));
        assert_eq!(doc.line_col(2), (1, 3));
        assert_eq!(doc.line_col(3), (2, 1));
        assert_eq!(doc.line_col(5), (2, 3));
    }
}
