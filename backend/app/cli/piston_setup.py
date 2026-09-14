"""Idempotent Piston package installer — run via `make piston-setup`.

Piston ships with no languages preinstalled; this installs Python, Java, and
C# (via the `dotnet` package — Piston has no standalone "csharp" package)
against the running `piston` container's live package API, skipping any
already installed. See app/services/coding/runtimes.py for the exact
versions, verified against Piston's /api/v2/packages at the time this was
written — re-check that endpoint before changing them.
"""

import asyncio

import httpx

from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.services.coding.runtimes import RUNTIME_VERSIONS

configure_logging(debug=True)
logger = get_logger(__name__)

# Piston's package name doesn't always match the /execute language name
# (e.g. C# installs via "dotnet" but executes as "csharp.net").
PACKAGE_NAME = {
    "python": "python",
    "java": "java",
    "csharp": "dotnet",
}


async def main() -> None:
    settings = get_settings()
    async with httpx.AsyncClient(base_url=settings.piston_base_url, timeout=120.0) as client:
        response = await client.get("/api/v2/packages")
        response.raise_for_status()
        installed = {
            (pkg["language"], pkg["language_version"])
            for pkg in response.json()
            if pkg.get("installed")
        }

        for language, version in RUNTIME_VERSIONS.items():
            package = PACKAGE_NAME[language]
            if (package, version) in installed:
                logger.info("piston_setup.already_installed", package=package, version=version)
                continue

            logger.info("piston_setup.installing", package=package, version=version)
            install = await client.post(
                "/api/v2/packages", json={"language": package, "version": version}
            )
            if install.status_code >= 400:
                logger.error(
                    "piston_setup.install_failed",
                    package=package,
                    version=version,
                    status=install.status_code,
                    body=install.text,
                )
                install.raise_for_status()
            logger.info("piston_setup.installed", package=package, version=version)

    logger.info("piston_setup.done")


if __name__ == "__main__":
    asyncio.run(main())
