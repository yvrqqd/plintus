//! tree-sitter parse → normalized Document.

use crate::document::{build_line_starts, Document, NodeData, Span};
use std::collections::HashMap;
use tree_sitter::{Node, Parser, Tree};

/// Iterative tree walk with an explicit stack. Avoids stack overflow on
/// deeply nested expressions (generated/pathological inputs).
fn walk_iter(
    root: Node<'_>,
    nodes: &mut Vec<NodeData>,
    kind_index: &mut HashMap<&'static str, Vec<u32>>,
) {
    struct Frame<'a> {
        node: Node<'a>,
        id: u32,
        next_child: usize,
    }

    let root_id = nodes.len() as u32;
    let root_kind: &'static str = root.kind();
    nodes.push(NodeData {
        kind: root_kind,
        span: Span {
            start: root.start_byte(),
            end: root.end_byte(),
        },
        parent: None,
        children: Vec::new(),
        named: root.is_named(),
    });
    kind_index.entry(root_kind).or_default().push(root_id);

    let mut stack: Vec<Frame<'_>> = vec![Frame {
        node: root,
        id: root_id,
        next_child: 0,
    }];

    while let Some(frame) = stack.last_mut() {
        match frame.node.child(frame.next_child) {
            Some(child) => {
                frame.next_child += 1;
                let cid = nodes.len() as u32;
                let kind: &'static str = child.kind();
                nodes.push(NodeData {
                    kind,
                    span: Span {
                        start: child.start_byte(),
                        end: child.end_byte(),
                    },
                    parent: Some(frame.id),
                    children: Vec::new(),
                    named: child.is_named(),
                });
                kind_index.entry(kind).or_default().push(cid);
                nodes[frame.id as usize].children.push(cid);
                stack.push(Frame {
                    node: child,
                    id: cid,
                    next_child: 0,
                });
            }
            None => {
                stack.pop();
            }
        }
    }
}

thread_local! {
    // Thread-local parser pool: avoids allocating a fresh `Parser` (and
    // re-setting the language) on every parse. The parser carries the parser
    // stack and is the expensive part to recreate.
    static PARSER: std::cell::RefCell<Option<Parser>> = const { std::cell::RefCell::new(None) };
}

/// Thread-local parser pool helper.
fn with_parser<F, R>(f: F) -> R
where
    F: FnOnce(&mut Parser) -> R,
{
    PARSER.with(|cell| {
        let mut slot = cell.borrow_mut();
        let parser = slot.get_or_insert_with(|| {
            let mut p = Parser::new();
            let language = tree_sitter_python::LANGUAGE;
            // Setting the language is cheap but not free; do it once per parser.
            let _ = p.set_language(&language.into());
            p
        });
        f(parser)
    })
}

pub fn parse_source(path: &str, source: &str) -> Result<Document, String> {
    let tree: Tree = with_parser(|parser| parser.parse(source, None))
        .ok_or_else(|| "tree-sitter parse returned None".to_string())?;

    let mut nodes = Vec::new();
    let mut kind_index: HashMap<&'static str, Vec<u32>> = HashMap::new();
    walk_iter(tree.root_node(), &mut nodes, &mut kind_index);

    Ok(Document {
        path: path.to_string(),
        source: source.to_string(),
        nodes,
        kind_index,
        line_starts: build_line_starts(source),
    })
}

/// Parse and return timing in microseconds (parse+index).
pub fn parse_source_timed(path: &str, source: &str) -> Result<(Document, u128), String> {
    let start = std::time::Instant::now();
    let doc = parse_source(path, source)?;
    Ok((doc, start.elapsed().as_micros()))
}
