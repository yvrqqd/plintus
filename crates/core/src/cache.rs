//! Content-addressed lint cache.

use sha2::{Digest, Sha256};
use std::fs;
use std::path::{Path, PathBuf};

/// Cache keys must be lowercase hex digests. Rejects anything containing
/// path separators, `..`, or non-hex chars — prevents path traversal via
/// `cache_path(dir, key)`.
fn validate_key(key: &str) -> Result<(), String> {
    if key.is_empty() || !key.chars().all(|c| c.is_ascii_hexdigit()) {
        return Err(format!("invalid cache key (expected hex digest): {key:?}"));
    }
    Ok(())
}

pub fn hash_bytes(data: &[u8]) -> String {
    let mut hasher = Sha256::new();
    hasher.update(data);
    hex::encode(hasher.finalize())
}

pub fn cache_key(source: &str, config_hash: &str, rules_hash: &str) -> String {
    let mut hasher = Sha256::new();
    hasher.update(source.as_bytes());
    hasher.update(b"\0");
    hasher.update(config_hash.as_bytes());
    hasher.update(b"\0");
    hasher.update(rules_hash.as_bytes());
    hex::encode(hasher.finalize())
}

pub fn cache_path(dir: &Path, key: &str) -> Result<PathBuf, String> {
    validate_key(key)?;
    Ok(dir.join(format!("{key}.json")))
}

/// Returns `Ok(None)` on cache miss (file not found), `Ok(Some(payload))` on hit,
/// and `Err` on any I/O error that is not a missing file. Distinguishes miss
/// from corrupt/permission-denied so callers can surface real problems.
pub fn read_cache(dir: &Path, key: &str) -> Result<Option<String>, String> {
    let path = cache_path(dir, key)?;
    match fs::read_to_string(&path) {
        Ok(s) => Ok(Some(s)),
        Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(None),
        Err(e) => Err(format!("cache read failed for {path:?}: {e}")),
    }
}

pub fn write_cache(dir: &Path, key: &str, payload: &str) -> Result<(), String> {
    validate_key(key)?;
    fs::create_dir_all(dir).map_err(|e| format!("cache create_dir_all failed: {e}"))?;
    let path = cache_path(dir, key)?;
    // Unique tmp file per process+write to avoid concurrent same-key clobbering.
    let tmp = path.with_extension(format!(
        "{}.{}.tmp",
        std::process::id(),
        tmp_suffix()
    ));
    fs::write(&tmp, payload).map_err(|e| format!("cache write failed: {e}"))?;
    fs::rename(&tmp, &path).map_err(|e| {
        // best-effort cleanup of orphaned tmp
        let _ = fs::remove_file(&tmp);
        format!("cache rename failed: {e}")
    })?;
    Ok(())
}

fn tmp_suffix() -> u64 {
    use std::sync::atomic::{AtomicU64, Ordering};
    static COUNTER: AtomicU64 = AtomicU64::new(0);
    COUNTER.fetch_add(1, Ordering::Relaxed)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn rejects_non_hex_keys() {
        assert!(cache_path(Path::new("/tmp"), "../escape").is_err());
        assert!(cache_path(Path::new("/tmp"), "abc/def").is_err());
        assert!(cache_path(Path::new("/tmp"), "").is_err());
        assert!(cache_path(Path::new("/tmp"), "XYZ123").is_err());
    }

    #[test]
    fn accepts_hex_keys() {
        let key = "abcdef0123456789".repeat(4); // 64 hex chars
        let p = cache_path(Path::new("/tmp"), &key).unwrap();
        assert_eq!(p, Path::new("/tmp").join(format!("{key}.json")));
    }

    #[test]
    fn read_cache_missing_is_none() {
        let dir = std::env::temp_dir().join("plintus_cache_test_missing");
        let _ = fs::remove_dir_all(&dir);
        let key = "abcdef0123456789".repeat(4);
        assert_eq!(read_cache(&dir, &key).unwrap(), None);
    }

    #[test]
    fn write_then_read_roundtrip() {
        let dir = std::env::temp_dir().join("plintus_cache_test_rt");
        let _ = fs::remove_dir_all(&dir);
        let key = "deadbeef".repeat(8);
        write_cache(&dir, &key, "{\"hello\":1}").unwrap();
        assert_eq!(read_cache(&dir, &key).unwrap(), Some("{\"hello\":1}".to_string()));
        let _ = fs::remove_dir_all(&dir);
    }

    #[test]
    fn write_rejects_bad_key() {
        let dir = std::env::temp_dir().join("plintus_cache_test_bad");
        let _ = fs::remove_dir_all(&dir);
        assert!(write_cache(&dir, "../escape", "x").is_err());
        let _ = fs::remove_dir_all(&dir);
    }
}
