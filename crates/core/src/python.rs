//! PyO3 extension surface — gated behind the `python` feature.

use crate::document::SharedDocument;
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyDict, PyList};
use std::path::PathBuf;
use std::sync::Arc;

/// Owned CST document exposed to Python. Lifetime is tied to the Python object:
/// when the `PyDocument` is garbage-collected, the underlying `Arc<Document>`
/// drops (and frees source + node array). No global registry, no manual
/// `drop_document`, no leak on forgotten `close()`.
#[pyclass(module = "plintus._core", name = "PyDocument")]
pub struct PyDocument {
    pub(crate) doc: SharedDocument,
}

impl PyDocument {
    fn new(doc: SharedDocument) -> Self {
        Self { doc }
    }
}

#[pymethods]
impl PyDocument {
    #[getter]
    fn path(&self) -> &str {
        &self.doc.path
    }

    #[getter]
    fn source(&self) -> &str {
        &self.doc.source
    }

    #[getter]
    fn node_count(&self) -> usize {
        self.doc.nodes.len()
    }

    fn select(&self, kinds: Vec<String>) -> Vec<u32> {
        self.doc.select(&kinds)
    }

    fn all_nodes(&self) -> Vec<u32> {
        self.doc.all_nodes()
    }

    fn node_kind(&self, id: u32) -> PyResult<&str> {
        self.doc
            .node(id)
            .map(|n| n.kind)
            .ok_or_else(|| PyValueError::new_err("invalid node id"))
    }

    fn node_span(&self, id: u32) -> PyResult<(usize, usize)> {
        self.doc
            .node(id)
            .map(|n| (n.span.start, n.span.end))
            .ok_or_else(|| PyValueError::new_err("invalid node id"))
    }

    fn node_text(&self, id: u32) -> PyResult<&str> {
        self.doc
            .text_of(id)
            .ok_or_else(|| PyValueError::new_err("invalid node id"))
    }

    fn node_parent(&self, id: u32) -> PyResult<Option<u32>> {
        self.doc
            .node(id)
            .map(|n| n.parent)
            .ok_or_else(|| PyValueError::new_err("invalid node id"))
    }

    fn node_children(&self, id: u32) -> PyResult<Vec<u32>> {
        self.doc
            .node(id)
            .map(|n| n.children.clone())
            .ok_or_else(|| PyValueError::new_err("invalid node id"))
    }

    fn node_ancestors(&self, id: u32) -> PyResult<Vec<u32>> {
        self.doc
            .ancestors(id)
            .map_err(|_| PyValueError::new_err("invalid node id"))
    }

    fn node_line_col(&self, id: u32) -> PyResult<(usize, usize, usize, usize)> {
        let n = self
            .doc
            .node(id)
            .ok_or_else(|| PyValueError::new_err("invalid node id"))?;
        let (sl, sc) = self.doc.line_col(n.span.start);
        let (el, ec) = self.doc.line_col(n.span.end);
        Ok((sl, sc, el, ec))
    }

    /// Batch node metadata for a list of ids — reduces FFI round-trips.
    /// Builds the Python list without holding any global lock (the document is
    /// owned by this PyDocument, so there is no contention).
    fn nodes_batch<'py>(
        &self,
        py: Python<'py>,
        node_ids: Vec<u32>,
    ) -> PyResult<Bound<'py, PyList>> {
        let list = PyList::empty(py);
        for id in node_ids {
            let n = self
                .doc
                .node(id)
                .ok_or_else(|| PyValueError::new_err(format!("invalid node id {id}")))?;
            let dict = PyDict::new(py);
            dict.set_item("id", id)?;
            dict.set_item("kind", n.kind)?;
            dict.set_item("start", n.span.start)?;
            dict.set_item("end", n.span.end)?;
            dict.set_item("parent", n.parent)?;
            dict.set_item("named", n.named)?;
            let text = self.doc.source.get(n.span.start..n.span.end).unwrap_or("");
            dict.set_item("text", text)?;
            let (sl, sc) = self.doc.line_col(n.span.start);
            dict.set_item("line", sl)?;
            dict.set_item("col", sc)?;
            list.append(dict)?;
        }
        Ok(list)
    }

    fn __len__(&self) -> usize {
        self.doc.nodes.len()
    }
}

/// Parse a Python source string into a normalized CST document.
/// Returns (PyDocument, parse_micros).
#[pyfunction]
fn parse_file(py: Python<'_>, path: &str, source: &str) -> PyResult<(Py<PyDocument>, u128)> {
    let result = py.allow_threads(|| crate::parse::parse_source_timed(path, source));
    let (doc, micros) = result.map_err(PyValueError::new_err)?;
    let py_doc = Py::new(py, PyDocument::new(Arc::new(doc)))?;
    Ok((py_doc, micros))
}

#[pyfunction]
#[pyo3(name = "discover")]
fn discover_files(paths: Vec<String>) -> PyResult<Vec<String>> {
    let roots: Vec<PathBuf> = paths.into_iter().map(PathBuf::from).collect();
    let files = Python::with_gil(|py| {
        py.allow_threads(|| crate::discover::discover_python_files(&roots))
    })
    .map_err(|e| {
        use pyo3::exceptions::PyFileNotFoundError;
        // "path does not exist: <p>" → FileNotFoundError; anything else → ValueError.
        if e.starts_with("path does not exist:") {
            PyFileNotFoundError::new_err(e)
        } else {
            PyValueError::new_err(e)
        }
    })?;
    Ok(files
        .into_iter()
        .map(|p| p.to_string_lossy().into_owned())
        .collect())
}

#[pyfunction]
fn hash_text(text: &str) -> PyResult<String> {
    Ok(crate::cache::hash_bytes(text.as_bytes()))
}

#[pyfunction]
fn make_cache_key(source: &str, config_hash: &str, rules_hash: &str) -> PyResult<String> {
    Ok(crate::cache::cache_key(source, config_hash, rules_hash))
}

#[pyfunction]
fn cache_read(dir: &str, key: &str) -> PyResult<Option<String>> {
    crate::cache::read_cache(std::path::Path::new(dir), key).map_err(PyValueError::new_err)
}

#[pyfunction]
fn cache_write(dir: &str, key: &str, payload: &str) -> PyResult<()> {
    crate::cache::write_cache(std::path::Path::new(dir), key, payload).map_err(PyValueError::new_err)
}

#[pyfunction]
fn api_version() -> &'static str {
    "1"
}

/// Register the `_core` module. Called by the `#[pymodule]` factory.
pub fn register_module(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_class::<PyDocument>()?;
    m.add_function(wrap_pyfunction!(parse_file, m)?)?;
    m.add_function(wrap_pyfunction!(discover_files, m)?)?;
    m.add_function(wrap_pyfunction!(hash_text, m)?)?;
    m.add_function(wrap_pyfunction!(make_cache_key, m)?)?;
    m.add_function(wrap_pyfunction!(cache_read, m)?)?;
    m.add_function(wrap_pyfunction!(cache_write, m)?)?;
    m.add_function(wrap_pyfunction!(api_version, m)?)?;
    Ok(())
}

#[pymodule]
fn _core(m: &Bound<'_, PyModule>) -> PyResult<()> {
    register_module(m)
}
