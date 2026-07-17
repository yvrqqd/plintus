//! plintus_core — Rust CST core.
//!
//! The pure-Rust modules (cache, discover, document, parse) are always built
//! and unit-testable without Python. The PyO3 extension surface is gated
//! behind the `python` feature, which maturin enables for wheel builds.

mod cache;
mod discover;
mod document;
mod parse;

#[cfg(feature = "python")]
mod python;

#[cfg(feature = "python")]
pub use python::register_module;
