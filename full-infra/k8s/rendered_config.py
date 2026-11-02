"""Read one value out of a `helm template` render.

Why this exists
---------------
The deploy workflow publishes the database endpoint it actually rendered to
$GITHUB_ENV, so the preflight Job, the prerequisite checks and `helm upgrade`
cannot disagree about which database production is about to use. That is only
worth anything if the value read back out of the manifest is the value the
manifest holds.

It used to be read with `grep | sed -E 's/...([^"]*).../\\1/'`. That is not
portable: sed implementations disagree about what a back-reference in the
*replacement* means, and one of them expands `\\1` as the octal escape 0x01.
The workflow would then have exported a single control byte as the DB host -
not a hostname, published to every later step, with nothing in the logs saying
why the database could not be resolved.

This file reads the value instead. It has one meaning on every platform, it is
importable, and full-infra/k8s/verify_chart_and_workflow.py exercises it against the
manifest `helm template` really produces.

Usage
-----
    python3 full-infra/k8s/rendered_config.py rendered.yaml \\
        ConfigMap data.ODOO_DB_HOST
    python3 full-infra/k8s/rendered_config.py rendered.yaml \\
        PersistentVolumeClaim spec.storageClassName

Prints the unquoted scalar and exits 0. Prints nothing and exits 1 when the
document kind or the path is absent - so a shell caller can make an optional
value optional with `|| true` - and exits 2 on a usage error.
"""
import sys

DOCUMENT_SEPARATOR = "---"
KEY_SEPARATOR = ":"
LIST_ITEM_PREFIX = "- "
COMMENT_PREFIX = "#"
QUOTES = ("\"", "'")


def split_documents(manifest_text):
    """Split a multi-document YAML stream into one line list per document."""
    documents = []
    current = []
    for line in manifest_text.splitlines():
        if line.strip() == DOCUMENT_SEPARATOR:
            documents.append(current)
            current = []
        else:
            current.append(line)
    documents.append(current)
    return documents


def _document_kind(lines):
    for line in lines:
        if line[:1].isspace():
            continue
        key, separator, value = line.rstrip().partition(KEY_SEPARATOR)
        if separator and key.strip() == "kind":
            return value.strip()
    return None


def read_manifest_file(path):
    """Read a manifest as text, whatever byte encoding it was redirected with.

    `helm template > file` in bash writes UTF-8; the same redirection from a
    Windows shell writes UTF-16 with a BOM. The bytes are decoded here so a
    developer running the deploy checks locally gets the same answer as the
    runner, instead of a UnicodeDecodeError instead of a DB host.
    """
    with open(path, "rb") as handle:
        raw_bytes = handle.read()
    if raw_bytes.startswith((b"\xff\xfe", b"\xfe\xff")):
        return raw_bytes.decode("utf-16")
    return raw_bytes.decode("utf-8-sig", errors="replace")


def _unquote(raw_value):
    value = raw_value.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in QUOTES:
        return value[1:-1]
    return value


def read_value(manifest_text, kind, dotted_path):
    """Return the scalar at `dotted_path` inside the first document of `kind`.

    `dotted_path` is the mapping path below the document root, e.g.
    "data.ODOO_DB_HOST" for a ConfigMap entry or "spec.storageClassName" for a
    PVC field. Returns None when the document, the path or a non-empty scalar
    is absent.
    """
    wanted_path = dotted_path.split(".")
    for lines in split_documents(manifest_text):
        if _document_kind(lines) != kind:
            continue
        found = _walk(lines, wanted_path)
        if found is not None:
            return found
    return None


def _walk(lines, wanted_path):
    open_blocks = []
    for raw_line in lines:
        line = raw_line.rstrip()
        stripped = line.strip()
        if (not stripped
                or stripped.startswith((COMMENT_PREFIX, LIST_ITEM_PREFIX))):
            continue
        key, separator, value = stripped.partition(KEY_SEPARATOR)
        if not separator:
            continue
        indent = len(line) - len(line.lstrip(" "))
        while open_blocks and open_blocks[-1][0] >= indent:
            open_blocks.pop()
        current_path = [block_key for _, block_key in open_blocks]
        current_path.append(key.strip())
        if current_path == wanted_path:
            return _unquote(value) or None
        if not value.strip():
            open_blocks.append((indent, key.strip()))
    return None


def main(argv):
    if len(argv) != 4:
        sys.stderr.write(
            "usage: rendered_config.py <manifest> <Kind> <dotted.path>\n")
        return 2
    manifest_path, kind, dotted_path = argv[1], argv[2], argv[3]
    try:
        manifest_text = read_manifest_file(manifest_path)
    except OSError as error:
        sys.stderr.write("cannot read " + manifest_path + ": " + str(error) + "\n")
        return 1

    value = read_value(manifest_text, kind, dotted_path)
    if value is None:
        return 1
    sys.stdout.write(value + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
