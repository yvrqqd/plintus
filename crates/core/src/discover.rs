//! File discovery with .gitignore support.

use ignore::WalkBuilder;
use std::path::{Path, PathBuf};

pub fn discover_python_files(roots: &[PathBuf]) -> Result<Vec<PathBuf>, String> {
    let mut files = Vec::new();
    for root in roots {
        if root.is_file() {
            if is_python(root) {
                files.push(root.clone());
            }
            continue;
        }
        if !root.exists() {
            return Err(format!("path does not exist: {}", root.display()));
        }
        let walker = WalkBuilder::new(root)
            .hidden(false)
            .git_ignore(true)
            .git_global(true)
            .git_exclude(true)
            .build();
        for entry in walker {
            let entry = entry.map_err(|e| e.to_string())?;
            let path = entry.path();
            if path.is_file() && is_python(path) {
                files.push(path.to_path_buf());
            }
        }
    }
    files.sort();
    files.dedup();
    Ok(files)
}

fn is_python(path: &Path) -> bool {
    matches!(
        path.extension().and_then(|s| s.to_str()),
        Some("py" | "pyi")
    )
}

#[cfg(test)]
mod tests {
    use super::*;

    fn tmp() -> PathBuf {
        use std::sync::atomic::{AtomicU64, Ordering};
        static COUNTER: AtomicU64 = AtomicU64::new(0);
        let id = COUNTER.fetch_add(1, Ordering::Relaxed);
        let dir = std::env::temp_dir().join(format!(
            "plintus_discover_{}_{}",
            std::process::id(),
            id
        ));
        let _ = std::fs::remove_dir_all(&dir);
        std::fs::create_dir_all(&dir).unwrap();
        dir
    }

    #[test]
    fn missing_path_is_err() {
        let r = discover_python_files(&[PathBuf::from("/nonexistent/definitely/missing")]);
        assert!(r.is_err());
        assert!(r.unwrap_err().starts_with("path does not exist"));
    }

    #[test]
    fn discovers_py_and_pyi() {
        let dir = tmp();
        std::fs::write(dir.join("a.py"), "x=1").unwrap();
        std::fs::write(dir.join("b.pyi"), "x: int").unwrap();
        std::fs::write(dir.join("c.txt"), "ignore").unwrap();
        let files = discover_python_files(&[dir.clone()]).unwrap();
        let names: Vec<_> = files.iter().map(|p| p.file_name().unwrap().to_string_lossy().into_owned()).collect();
        assert!(names.contains(&"a.py".to_string()));
        assert!(names.contains(&"b.pyi".to_string()));
        assert!(!names.contains(&"c.txt".to_string()));
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn single_file_root_py() {
        let dir = tmp();
        let f = dir.join("single.py");
        std::fs::write(&f, "x=1").unwrap();
        let files = discover_python_files(&[f.clone()]).unwrap();
        assert_eq!(files, vec![f]);
        let _ = std::fs::remove_dir_all(&dir);
    }

    #[test]
    fn parse_builds_document() {
        let src = "def f(x):\n    return x\n";
        let doc = crate::parse::parse_source("t.py", src).unwrap();
        assert_eq!(doc.path, "t.py");
        assert_eq!(doc.source, src);
        assert!(doc.nodes.len() > 5);
        assert!(doc.kind_index.contains_key("function_definition"));
        assert_eq!(doc.line_starts, vec![0, 10, 23]);
    }

    #[test]
    fn parse_invalid_syntax_still_recovers() {
        let src = "def broken(\n    pass\n";
        let doc = crate::parse::parse_source("bad.py", src).unwrap();
        // tree-sitter error recovery yields some nodes
        assert!(!doc.nodes.is_empty());
    }

    #[test]
    fn parse_select_by_kind() {
        let doc = crate::parse::parse_source("t.py", "x = 1\ny = 2\n").unwrap();
        let idents = doc.select(&["identifier".to_string()]);
        assert!(!idents.is_empty());
        // empty kinds returns empty (not all nodes)
        assert!(doc.select(&[]).is_empty());
        let all = doc.all_nodes();
        assert!(all.len() > idents.len());
    }

    #[test]
    fn parse_ancestors_invalid() {
        let doc = crate::parse::parse_source("t.py", "x = 1\n").unwrap();
        assert!(doc.ancestors(0).is_ok());
        assert!(doc.ancestors(999_999).is_err());
    }
}
