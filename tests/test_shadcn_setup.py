"""D-402: shadcn_setup patches a fresh Vite project the way the shadcn CLI expects, and a certificate failure is recognised and handled.

The patch functions are tested on the files `npm create vite@latest --template react-ts` writes. The whole tool (npm and shadcn from the network) runs only
when FORGE_NETWORK_TESTS=1 is set: it needs the internet and takes minutes."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

from forge.net import looks_like_certificate_error, windows_certificate_bundle
from forge.tools.shadcn import (
    dependency_names,
    patch_index_css,
    patch_tsconfig,
    patch_vite_config,
)

VITE_CONFIG = """import react from '@vitejs/plugin-react'
import { defineConfig } from 'vite'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react()],
})
"""
TSCONFIG = """{
  "files": [],
  "references": [
    { "path": "./tsconfig.app.json" },
    { "path": "./tsconfig.node.json" }
  ]
}
"""
TSCONFIG_APP = """{
  "compilerOptions": {
    "target": "es2023",

    /* Bundler mode */
    "moduleResolution": "bundler",
    "jsx": "react-jsx"
  },
  "include": ["src"]
}
"""


def test_the_vite_config_gets_the_tailwind_plugin_and_the_alias_once() -> None:
    patched = patch_vite_config(VITE_CONFIG)
    assert patched is not None
    assert 'import tailwindcss from "@tailwindcss/vite"' in patched and 'import path from "path"' in patched
    assert "plugins: [tailwindcss(), react()]" in patched
    assert 'alias: { "@": path.resolve(__dirname, "./src") }' in patched
    assert patch_vite_config(patched) == patched  # running the setup again changes nothing


def test_an_unusual_vite_config_is_left_alone() -> None:
    assert patch_vite_config("export default {}\n") is None


def test_both_tsconfig_files_get_the_alias_and_keep_their_comments() -> None:
    root = patch_tsconfig(TSCONFIG)
    assert '"compilerOptions"' in root and '"@/*": ["./src/*"]' in root and '"references"' in root
    app = patch_tsconfig(TSCONFIG_APP)
    assert '"paths": { "@/*": ["./src/*"] },' in app and "/* Bundler mode */" in app
    assert patch_tsconfig(app) == app


def test_the_stylesheet_imports_tailwind_first_and_keeps_the_template_rules() -> None:
    patched = patch_index_css(":root { --x: 1; }\n")
    assert patched.startswith('@import "tailwindcss";') and ":root { --x: 1; }" in patched
    assert patch_index_css(patched) == patched
    assert patch_index_css("") == '@import "tailwindcss";\n'


def test_dependencies_are_read_from_both_sections() -> None:
    assert dependency_names('{"dependencies": {"react": "1"}, "devDependencies": {"vite": "2"}}') == {
        "react",
        "vite",
    }
    assert dependency_names("not json") == set()


@pytest.mark.parametrize(
    "text",
    [
        "npm error code UNABLE_TO_GET_ISSUER_CERT_LOCALLY\nnpm error unable to get local issuer certificate",
        "Error: self-signed certificate in certificate chain",
        "curl: (60) SSL certificate problem: unable to get local issuer certificate",
        "UNABLE_TO_VERIFY_LEAF_SIGNATURE",
    ],
)
def test_certificate_failures_are_recognised(text: str) -> None:
    assert looks_like_certificate_error(text)


def test_other_failures_are_not_certificate_failures() -> None:
    assert not looks_like_certificate_error("npm error 404 Not Found - GET https://registry.npmjs.org/nope")


@pytest.mark.skipif(sys.platform != "win32", reason="the Windows certificate store")
def test_the_windows_certificates_are_written_as_one_pem_file(tmp_path: Path) -> None:
    import ssl

    bundle = windows_certificate_bundle(tmp_path / "certs" / "roots.pem")
    assert bundle is not None and bundle.is_file()
    text = bundle.read_text(encoding="ascii")
    assert text.count("BEGIN CERTIFICATE") >= 5
    context = ssl.create_default_context(cafile=str(bundle))  # a file Python itself accepts as a CA list
    assert context.cert_store_stats()["x509_ca"] >= 5


def test_the_advice_after_a_certificate_failure_switches_to_the_bundle_once() -> None:
    from forge.toolkit.shell import certificate_advice

    class Stub:
        ca_bundle: Path | None = None

        def prepare_ca_bundle(self, force: bool = False) -> bool:
            self.ca_bundle = Path("bundle.pem")
            return True

    shell = Stub()
    first = certificate_advice(shell)  # type: ignore[arg-type]
    assert "run the same command again" in first and "NODE_EXTRA_CA_CERTS" in first
    second = certificate_advice(shell)  # type: ignore[arg-type]
    assert (
        "already in use" in second
        and "Tell the user" in second
        and "NODE_TLS_REJECT_UNAUTHORIZED=0" in second
    )


@pytest.mark.skipif(
    os.environ.get("FORGE_NETWORK_TESTS") != "1" or shutil.which("npm") is None,
    reason="set FORGE_NETWORK_TESTS=1 (needs npm and the internet, takes minutes)",
)
async def test_the_whole_setup_on_a_new_project(tmp_path: Path, original_repo: Path) -> None:
    from forge.toolkit.base import ToolContext
    from forge.toolkit.shell import ShellSession
    from forge.tools.shadcn import ShadcnSetup
    from forge.workspace.create import create_workspace

    workspace = create_workspace(original_repo, tmp_path / "ws", "backend")
    context = ToolContext(workspace=workspace)
    context.shell = ShellSession(workspace, sandbox="off")  # type: ignore[arg-type]
    result = await ShadcnSetup().run(ShadcnSetup.Args(project_dir="web", components=["button"]), context)
    assert result.ok, result.content
    web = workspace.repo_dir / "web"
    assert (web / "components.json").is_file() and (
        web / "src" / "components" / "ui" / "button.tsx"
    ).is_file()
    again = await ShadcnSetup().run(ShadcnSetup.Args(project_dir="web"), context)
    assert again.ok, again.content
