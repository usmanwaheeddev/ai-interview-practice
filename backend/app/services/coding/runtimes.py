"""Piston runtime names/versions actually installed by the `piston-setup`
Makefile target (see docker-compose.yml's `piston` service) — verified
against Piston's live /api/v2/packages, not memory. Piston has no standalone
"csharp" package: C# ships inside the `dotnet` package, and its runtime name
for /execute is "csharp.net"."""

RUNTIME_VERSIONS = {
    "python": "3.12.0",
    "java": "15.0.2",
    "csharp": "5.0.201",
}

PISTON_LANGUAGE_NAME = {
    "python": "python",
    "java": "java",
    "csharp": "csharp.net",
}
