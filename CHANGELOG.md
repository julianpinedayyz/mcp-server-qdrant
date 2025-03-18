# Changelog

All notable changes to the MCP Server Qdrant project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- **Structured Logging System**
  - Added a new `logging.py` module with JSON formatting for logs
  - Implemented correlation IDs for request tracing across components
  - Added context-rich logging helpers (`debug`, `info`, `warning`, `error`, `critical`)
  - Added `CorrelationIdFilter` for automatic correlation ID generation and propagation

- **Custom Exception Hierarchy**
  - Created a new `exceptions.py` module with a comprehensive exception hierarchy
  - Implemented base `MCPServerQdrantError` exception class
  - Added specific exceptions for different error categories:
    - `ConfigurationError`: For issues with configuration and settings
    - `ConnectionError`: For issues connecting to external services
    - `EmbeddingError`: For problems with embedding generation
    - `CollectionError`: For issues with collection management
    - `StoreError`: For problems storing entries
    - `SearchError`: For errors during search operations

- **Enhanced Error Handling**
  - Updated all core components with comprehensive error handling
  - Added detailed context to all exception instances
  - Improved error reporting with structured error data
  - Implemented proper error propagation to clients

- **Command-line Enhancements**
  - Added `--log-level` option to control logging verbosity
  - Added `--json-logs` flag to toggle JSON log formatting
  - Improved help text for all command-line options

### Changed

- **Server Initialization**
  - Enhanced `server_lifespan` with staged error handling
  - Improved component initialization with better error context
  - Added correlation ID propagation throughout server lifecycle

- **API Tools**
  - Updated `qdrant-store` with detailed error handling and logging
  - Enhanced `qdrant-find` with better error reporting and context
  - Added proper error documentation to API method docstrings
  - Included optional `limit` parameter for search control

- **Error Reporting**
  - Improved user-facing error messages for better clarity
  - Enhanced error context for operations to aid debugging
  - Added better debug channel feedback for client applications

### Fixed

- Proper handling of connection errors to Qdrant server
- Better initialization sequence with appropriate error propagation
- Improved error handling for embedding provider initialization
