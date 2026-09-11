#!/usr/bin/env bash
# Install the built wheel and sdist into clean environments and import the SDK.
#
# Both CI and the release workflow run this, so the artifacts that reach PyPI get
# the same clean-install check as every pull request's. A library has no console
# script to run, so the check is the one thing every consumer does first: import
# the package, build a client, reach the resource namespaces, close it.
#
# The sdist run matters separately from the wheel: a packaging mistake that only
# breaks the source build (a missing file in [tool.hatch.build.targets.sdist], a
# backend that cannot build offline) is otherwise invisible until someone
# installs with --no-binary.
#
# Usage: scripts/smoke-dist.sh [dist-dir]
set -euo pipefail

dist="${1:-dist}"

shopt -s nullglob
wheels=("$dist"/*.whl)
sdists=("$dist"/*.tar.gz)
shopt -u nullglob

if [ "${#wheels[@]}" -ne 1 ] || [ "${#sdists[@]}" -ne 1 ]; then
    echo "expected one wheel and one sdist in $dist/, found ${#wheels[@]} and ${#sdists[@]}" >&2
    exit 1
fi

smoke() {
    local label="$1" artifact="$2" venv
    venv="$(mktemp -d)/venv"
    uv venv --quiet "$venv"
    uv pip install --quiet --python "$venv/bin/python" "$artifact"

    echo "$label: netskope $("$venv/bin/python" -c 'import netskope; print(netskope.__version__)')"

    # Construct the client the way a first-time user does. Credentials are
    # synthetic and the socket is blocked, so this proves the import graph and
    # the namespace properties are intact without reaching a tenant.
    "$venv/bin/python" - <<'PY'
import socket


def _refuse(*_args: object, **_kwargs: object) -> None:
    raise AssertionError("the smoke test tried to open a network connection")


socket.socket.connect = _refuse

# Imported after the patch, so even an import-time request would be caught.
from netskope import NetskopeClient

client = NetskopeClient(tenant="example.goskope.com", api_token="synthetic-token")
try:
    if client.alerts.with_response is None or client.aicc is None:
        raise SystemExit("client is missing a resource namespace")
finally:
    client.close()
PY
    echo "$label: client built, namespaces reached, closed"

    if [ "$label" = wheel ]; then
        # PEP 561: without this marker every consumer's type checker treats the
        # package as untyped. Read the archive rather than the installed tree, so
        # a stray marker left behind by an editable install cannot mask its absence.
        "$venv/bin/python" - "$artifact" <<'PY'
import sys
import zipfile

if "netskope/py.typed" not in zipfile.ZipFile(sys.argv[1]).namelist():
    sys.exit("wheel does not contain netskope/py.typed")
PY
        echo "$label: contains netskope/py.typed"
    fi
}

smoke wheel "${wheels[0]}"
smoke sdist "${sdists[0]}"
