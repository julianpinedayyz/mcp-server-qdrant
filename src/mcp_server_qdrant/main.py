import argparse
import logging
import sys
import traceback

from mcp_server_qdrant.logging import configure_logging, info, error, critical
from mcp_server_qdrant.exceptions import MCPServerQdrantError, ConfigurationError


def main():
    """
    Main entry point for the mcp-server-qdrant script defined
    in pyproject.toml. It runs the MCP server with a specific transport
    protocol.
    """
    # Configure logging first thing
    configure_logging(level=logging.INFO, json_format=True, include_correlation_id=True)
    logger = logging.getLogger(__name__)
    
    info(logger, "Starting MCP Server Qdrant")
    
    try:
        # Parse the command-line arguments to determine the transport protocol.
        parser = argparse.ArgumentParser(description="mcp-server-qdrant")
        parser.add_argument(
            "--transport",
            choices=["stdio", "sse"],
            default="stdio",
            help="Transport protocol to use: stdio (default) or sse (Server-Sent Events)"
        )
        parser.add_argument(
            "--log-level",
            choices=["debug", "info", "warning", "error", "critical"],
            default="info",
            help="Set the logging level (default: info)"
        )
        parser.add_argument(
            "--json-logs",
            action="store_true",
            default=True,
            help="Output logs in JSON format (default: True)"
        )
        args = parser.parse_args()
        
        # Configure logging based on command line arguments
        log_level = getattr(logging, args.log_level.upper())
        configure_logging(level=log_level, json_format=args.json_logs, include_correlation_id=True)
        
        info(
            logger, 
            "MCP Server configuration", 
            {"transport": args.transport, "log_level": args.log_level, "json_logs": args.json_logs}
        )

        # Import is done here to make sure environment variables are loaded
        # only after we make the changes.
        from mcp_server_qdrant.server import mcp

        info(logger, f"Starting MCP server with {args.transport} transport")
        mcp.run(transport=args.transport)
        
    except ConfigurationError as e:
        critical(
            logger, 
            f"Configuration error: {e.message}", 
            e.details, 
            exc_info=e.original_error
        )
        print(f"Error: {e.message}", file=sys.stderr)
        print("Please check your environment variables and configuration.", file=sys.stderr)
        sys.exit(1)
    except MCPServerQdrantError as e:
        critical(
            logger, 
            f"MCP Server error: {e.message}", 
            e.details, 
            exc_info=e.original_error
        )
        print(f"Error: {e.message}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        critical(
            logger, 
            "Unhandled exception", 
            {"error": str(e), "traceback": traceback.format_exc()}, 
            exc_info=e
        )
        print(f"Error: An unexpected error occurred: {str(e)}", file=sys.stderr)
        sys.exit(1)
