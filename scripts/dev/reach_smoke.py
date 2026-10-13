"""What can this machine reach? One run gives the complete picture for DebCraft's outside resources (TODO D5, D-328).

    .venv\\Scripts\\python scripts\\dev\\reach_smoke.py [--timeout 15] [--only images|libraries|fonts|services] [--out folder]

For every resource it makes one real request the way DebCraft would (the system certificate store is used, proxy settings are read from the
environment) and says OK, or what stopped it: the name does not resolve, the company's HTTPS inspection certificate is not trusted, a
proxy answered 407, the site is blocked (403, or a login page instead of data), no answer in time. The image sources are searched with
DebCraft's own code and one file is downloaded from each, so a pass means `find_image` and `fetch_image` work from here.

It writes reach-report.md and reach-report.json (no keys, no passwords: only names, addresses, status and timing) into --out (default
the current folder). Send those two files back to have the blocked resources worked around."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import sys
import time
from dataclasses import asdict, dataclass
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "src"))

from forge.config import load_secrets  # noqa: E402
from forge.net import connection_hint, root_cause, use_system_certificates  # noqa: E402
from forge.tools import image_sources  # noqa: E402
from forge.tools.findimage import _download_url  # noqa: E402

SAMPLE_QUERY = "house"


@dataclass
class Result:
    group: str
    name: str
    target: str
    ok: bool
    detail: str
    ms: int
    why: str = ""  # what to do when it failed
    skipped: bool = False  # not tried (an optional key is missing)


@dataclass
class Probe:
    group: str
    name: str
    url: str
    method: str = "GET"
    expect: str = "any"  # any, json, text, image
    headers: dict[str, str] | None = None
    body: dict | None = None  # type: ignore[type-arg]
    needs: str = ""  # the .env key a probe needs; skipped without it


# What DebCraft uses or may use, by group. Each is one real request.
PROBES = [
    Probe(
        "libraries",
        "GitHub raw files",
        "https://raw.githubusercontent.com/lucide-icons/lucide/main/README.md",
        expect="text",
    ),
    Probe("libraries", "GitHub API", "https://api.github.com/repos/shadcn-ui/ui", expect="json"),
    Probe("libraries", "shadcn registry", "https://ui.shadcn.com/r/index.json", expect="json"),
    Probe("libraries", "npm registry", "https://registry.npmjs.org/react/latest", expect="json"),
    Probe("libraries", "PyPI", "https://pypi.org/pypi/pytest/json", expect="json"),
    Probe(
        "libraries",
        "jsDelivr CDN",
        "https://cdn.jsdelivr.net/npm/lucide-static@latest/package.json",
        expect="json",
    ),
    Probe("libraries", "unpkg CDN", "https://unpkg.com/react@18/package.json", expect="json"),
    Probe(
        "libraries",
        "osv.dev (dependency audit)",
        "https://api.osv.dev/v1/query",
        method="POST",
        expect="json",
        body={"package": {"name": "jinja2", "ecosystem": "PyPI"}, "version": "2.4.1"},
    ),
    Probe(
        "fonts",
        "Google Fonts CSS",
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;700&display=swap",
        expect="text",
    ),
    Probe(
        "fonts",
        "Google Fonts files",
        "https://fonts.gstatic.com/s/inter/v13/UcC73FwrK3iLTeHuS_fvQtMwCp50KnMa1ZL7.woff2",
        expect="any",
    ),
    Probe(
        "fonts",
        "Fontsource catalogue (find_font)",
        "https://api.fontsource.org/v1/fonts/inter",
        expect="json",
    ),
    Probe(
        "fonts",
        "Fontsource font file (fetch_font)",
        "https://cdn.jsdelivr.net/fontsource/fonts/inter@latest/latin-400-normal.woff2",
        expect="any",
    ),
    Probe(
        "fonts",
        "Fontsource CDN",
        "https://cdn.jsdelivr.net/npm/@fontsource/inter/package.json",
        expect="json",
    ),
    Probe(
        "services",
        "Google Vertex AI (Gemini, images)",
        "https://us-central1-aiplatform.googleapis.com/",
        expect="any",
    ),
    Probe(
        "services",
        "Google sign-in (credentials refresh)",
        "https://oauth2.googleapis.com/token",
        method="POST",
        expect="any",
        body={},
    ),
    Probe("services", "MDN docs", "https://developer.mozilla.org/en-US/docs/Web/CSS", expect="text"),
]


def classify(error: BaseException) -> tuple[str, str]:
    """(short reason, what to do) for a failed request."""
    detail = root_cause(error)
    lowered = detail.lower()
    if isinstance(error, httpx.TimeoutException) or "timed out" in lowered:
        return (
            "no answer in time",
            "a proxy is probably required: set HTTPS_PROXY for your user, or the site is blocked",
        )
    if "certificate" in lowered or "ssl" in lowered:
        return "HTTPS certificate not trusted", connection_hint(detail)
    if "getaddrinfo" in lowered or "name or service" in lowered or "nodename" in lowered:
        return (
            "name does not resolve",
            "the company DNS does not know this host (blocked) or there is no network",
        )
    if "407" in lowered or "proxy" in lowered:
        return "proxy refused", connection_hint(detail)
    return detail[:100], connection_hint(detail)


def judge(response: httpx.Response, expect: str) -> tuple[bool, str, str]:
    """(ok, detail, why) for an answer."""
    code = response.status_code
    kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
    if code in (401, 403) and expect != "any":
        return (
            False,
            f"HTTP {code}",
            "the site refuses this machine or needs a login (a proxy block page is also common)",
        )
    if code == 407:
        return (
            False,
            "HTTP 407",
            "the proxy wants credentials: set HTTPS_PROXY with them, or ask for the host to be allowed",
        )
    if code >= 500:
        return False, f"HTTP {code}", "the site has a problem right now; try again later"
    if code >= 400 and expect != "any":
        return False, f"HTTP {code}", "the address answered but not with the resource (it may have moved)"
    if expect == "json" and "json" not in kind:
        return (
            False,
            f"HTTP {code}, got {kind or 'no type'} instead of data",
            "a proxy or login page answered in place of the site",
        )
    if expect == "image" and not kind.startswith("image/"):
        return (
            False,
            f"HTTP {code}, got {kind or 'no type'} instead of a picture",
            "a proxy or login page answered in place of the site",
        )
    return True, f"HTTP {code}, {kind or 'no type'}, {len(response.content) // 1024} KB", ""


async def run_probe(client: httpx.AsyncClient, probe: Probe, gate: asyncio.Semaphore) -> Result:
    started = time.perf_counter()
    async with gate:
        try:
            response = await client.request(probe.method, probe.url, headers=probe.headers, json=probe.body)
            ok, detail, why = judge(response, probe.expect)
        except (httpx.HTTPError, OSError) as error:
            ok, (detail, why) = False, classify(error)
    return Result(
        probe.group,
        probe.name,
        probe.url.split("?")[0],
        ok,
        detail,
        round((time.perf_counter() - started) * 1000),
        why,
    )


async def run_image_source(
    client: httpx.AsyncClient, name: str, key: str, gate: asyncio.Semaphore
) -> list[Result]:
    """Searches one image source with DebCraft's own provider, then downloads the first result the way fetch_image does."""
    out: list[Result] = []
    started = time.perf_counter()
    target = image_sources.PROVIDERS[name].__module__ + "." + name
    async with gate:
        try:
            found = await asyncio.wait_for(image_sources.PROVIDERS[name](client, SAMPLE_QUERY, 3, key), 25)
            detail = f"{len(found)} licensed result(s) for '{SAMPLE_QUERY}'"
            out.append(
                Result(
                    "images",
                    f"{name}: search",
                    target,
                    bool(found),
                    detail if found else "answered, but no licensed result",
                    round((time.perf_counter() - started) * 1000),
                    "" if found else "try another query; the licence filter may have removed everything",
                )
            )
        except image_sources.SourceError as error:
            out.append(
                Result(
                    "images",
                    f"{name}: search",
                    target,
                    False,
                    str(error),
                    round((time.perf_counter() - started) * 1000),
                    "see the message; a key problem is fixed in the .env file",
                )
            )
            return out
        except (httpx.HTTPError, OSError, TimeoutError) as error:
            detail, why = classify(error)
            out.append(
                Result(
                    "images",
                    f"{name}: search",
                    target,
                    False,
                    detail,
                    round((time.perf_counter() - started) * 1000),
                    why,
                )
            )
            return out
        if not found:
            return out
        started = time.perf_counter()
        try:
            url = await _download_url(client, found[0])
            response = await client.get(url)
            ok, detail, why = judge(response, "image")
            out.append(
                Result(
                    "images",
                    f"{name}: download",
                    url.split("?")[0],
                    ok,
                    detail,
                    round((time.perf_counter() - started) * 1000),
                    why,
                )
            )
        except (httpx.HTTPError, OSError, image_sources.SourceError) as error:
            detail, why = (
                classify(error) if not isinstance(error, image_sources.SourceError) else (str(error), "")
            )
            out.append(
                Result(
                    "images",
                    f"{name}: download",
                    found[0].download_url.split("?")[0],
                    False,
                    detail,
                    round((time.perf_counter() - started) * 1000),
                    why,
                )
            )
    return out


def settings_probes(secrets: object) -> list[Probe]:
    """Hosts named in the user's .env file (reachability only: no key is sent)."""
    probes = []
    get = getattr(secrets, "get")  # noqa: B009
    for label, name in (
        ("Azure OpenAI (main)", "AZURE_OPENAI_ENDPOINT"),
        ("Agent platform (Tavily search)", "TAVILY_TOOL_URL"),
    ):
        url = get(name)
        if url:
            probes.append(Probe("services", label, url, expect="any"))
    return probes


def environment_lines(secrets: object) -> list[str]:
    get = getattr(secrets, "get")  # noqa: B009
    proxies = {
        k: ("set" if os.environ.get(k) else "not set")
        for k in ("HTTPS_PROXY", "HTTP_PROXY", "NO_PROXY", "ALL_PROXY")
    }
    keys = {
        name: ("set" if get(name) else "not set")
        for name in (*image_sources.KEY_NAMES.values(), "GEMINI_IMAGE_MODEL", "GOOGLE_CLOUD_PROJECT")
    }
    return [
        f"Python {platform.python_version()} on {platform.platform()}",
        f"Windows certificate store used for HTTPS: {'yes' if use_system_certificates() else 'no (truststore missing or FORGE_SYSTEM_CERTS=0)'}",
        "Proxy variables: " + ", ".join(f"{k} {v}" for k, v in proxies.items()),
        "Keys and settings in the .env file: " + ", ".join(f"{k} {v}" for k, v in keys.items()),
    ]


def render(results: list[Result], environment: list[str]) -> str:
    lines = ["# Reachability report", "", *[f"- {line}" for line in environment], ""]
    tried = [r for r in results if not r.skipped]
    passed = sum(r.ok for r in tried)
    lines += [
        f"**{passed} of {len(tried)} resources reached** ({len(results) - len(tried)} optional ones skipped).",
        "",
    ]
    for group in dict.fromkeys(r.group for r in results):
        lines += [f"## {group}", "", "| Resource | Result | Detail | ms |", "|---|---|---|---|"]
        for r in (x for x in results if x.group == group):
            lines.append(
                f"| {r.name} | {'SKIP' if r.skipped else 'OK' if r.ok else 'FAIL'} | {r.detail}{' -> ' + r.why if r.why and not r.ok else ''} | {r.ms} |"
            )
        lines.append("")
    return "\n".join(lines)


async def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--timeout", type=float, default=15.0)
    parser.add_argument("--only", choices=["images", "libraries", "fonts", "services"])
    parser.add_argument("--out", default=".")
    args = parser.parse_args(argv)
    secrets = load_secrets()
    environment = environment_lines(secrets)
    print("\n".join(environment), "\n")
    gate = asyncio.Semaphore(8)
    async with httpx.AsyncClient(
        timeout=args.timeout, headers={"User-Agent": image_sources.USER_AGENT}, follow_redirects=True
    ) as client:
        tasks = []
        if args.only in (None, "images"):
            for name in image_sources.PROVIDERS:
                key_name = image_sources.KEY_NAMES.get(name)
                key = secrets.get(key_name) if key_name else ""
                if key_name and not key:
                    continue  # reported below as skipped
                tasks.append(run_image_source(client, name, key or "", gate))
        probes = [p for p in [*PROBES, *settings_probes(secrets)] if args.only in (None, p.group)]
        tasks += [run_probe(client, probe, gate) for probe in probes]
        gathered = await asyncio.gather(*tasks)
    results: list[Result] = []
    for item in gathered:
        results += item if isinstance(item, list) else [item]
    if args.only in (None, "images"):
        for name, key_name in image_sources.KEY_NAMES.items():
            if not secrets.get(key_name):
                results.append(
                    Result(
                        "images",
                        f"{name}: search",
                        "(skipped)",
                        False,
                        f"not tried: {key_name} is not in the .env file",
                        0,
                        "optional: get a free key from the site and add it to the .env file",
                        skipped=True,
                    )
                )
    order = {"images": 0, "libraries": 1, "fonts": 2, "services": 3}
    results.sort(key=lambda r: (order.get(r.group, 9), r.name))
    report = render(results, environment)
    print(report)
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    (out / "reach-report.md").write_text(report, encoding="utf-8")
    (out / "reach-report.json").write_text(
        json.dumps({"environment": environment, "results": [asdict(r) for r in results]}, indent=1),
        encoding="utf-8",
    )
    print(f"\nWrote {out / 'reach-report.md'} and {out / 'reach-report.json'}")
    return 0 if all(r.ok or r.skipped for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main(sys.argv[1:])))
