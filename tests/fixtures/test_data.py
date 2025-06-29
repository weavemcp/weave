"""Test data fixtures for Weave tests"""

# Sample WeaveMCP API responses
SAMPLE_ORGANIZATIONS_RESPONSE = {
    "success": True,
    "organizations": [
        {"slug": "testorg", "name": "Test Organization", "role": "admin"},
        {"slug": "anotherorg", "name": "Another Organization", "role": "member"},
    ],
    "default_organization": "testorg",
}

SAMPLE_DEFAULT_SERVER_RESPONSE = {
    "success": True,
    "server": {
        "id": "srv_abcd1234",
        "name": "Test Virtual Server",
        "endpoint_url": "https://proxy.atlaslabs.weavemcp.app/proxy/abcd1234",
        "access_token": "at_test_access_token_123456789",
        "organization": {"slug": "testorg", "name": "Test Organization"},
        "downstream_servers": [
            {
                "id": "ds_filesystem_001",
                "name": "filesystem",
                "type": "filesystem",
                "status": "active",
                "config": {"root_path": "/tmp/test"},
            },
            {
                "id": "ds_sqlite_001",
                "name": "sqlite",
                "type": "sqlite",
                "status": "active",
                "config": {"database_path": "/tmp/test.db"},
            },
        ],
        "created_at": "2024-01-01T00:00:00Z",
        "updated_at": "2024-01-01T00:00:00Z",
    },
}

SAMPLE_CONNECTION_DETAILS = {
    "name": "weavemcp-testorg",
    "endpoint_url": "https://proxy.atlaslabs.weavemcp.app/proxy/abcd1234",
    "access_token": "at_test_access_token_123456789",
    "server_id": "srv_abcd1234",
    "organization": "testorg",
    "description": "WeaveMCP virtual server for Test Organization",
    "downstream_count": 2,
}

# Sample Claude Desktop configurations
EMPTY_CLAUDE_CONFIG = {"mcpServers": {}}

CLAUDE_CONFIG_WITH_EXISTING_SERVERS = {
    "mcpServers": {
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
        "sqlite": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-sqlite",
                "--db-path",
                "/tmp/test.db",
            ],
        },
    }
}

CLAUDE_CONFIG_WITH_WEAVEMCP_SERVER = {
    "mcpServers": {
        "weavemcp-testorg": {"command": "weave", "args": ["proxy"]},
        "filesystem": {
            "command": "npx",
            "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
        },
    }
}

CLAUDE_CONFIG_WITH_OLD_WEAVEMCP = {
    "mcpServers": {
        "weavemcp-testorg": {
            "command": "npx",
            "args": [
                "-y",
                "@modelcontextprotocol/server-proxy",
                "https://proxy.atlaslabs.weavemcp.app/proxy/old123",
                "old_token_123",
            ],
        }
    }
}

# Sample WeaveMCP configuration files
SAMPLE_WEAVEMCP_CONFIG = {
    "servers": {
        "default": {"url": "https://atlaslabs.weavemcp.app", "alias": "default"}
    },
    "current_server": "default",
    "version": "0.1.0",
}

SAMPLE_WEAVEMCP_CONFIG_MULTI_SERVER = {
    "servers": {
        "default": {"url": "https://atlaslabs.weavemcp.app", "alias": "default"},
        "staging": {"url": "https://staging.weavemcp.app", "alias": "staging"},
        "local": {"url": "http://localhost:8000", "alias": "local"},
    },
    "current_server": "default",
    "version": "0.1.0",
}

# Test tokens and URLs
TEST_SERVER_URLS = {
    "production": "https://atlaslabs.weavemcp.app",
    "staging": "https://staging.weavemcp.app",
    "local": "http://localhost:8000",
}

TEST_API_TOKENS = {
    "valid": "wmp_test_valid_token_123456789abcdef",
    "invalid": "invalid_token_format",
    "expired": "wmp_test_expired_token_987654321fedcba",
}

# Error responses
ERROR_RESPONSES = {
    "unauthorized": {
        "success": False,
        "error": "Invalid or expired API token",
        "code": "unauthorized",
    },
    "not_found": {
        "success": False,
        "error": "No default virtual server found",
        "code": "not_found",
    },
    "server_error": {
        "success": False,
        "error": "Internal server error",
        "code": "server_error",
    },
}
