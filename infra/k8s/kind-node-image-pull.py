"""Fetch kindest/node as a ``docker load``-format tarball, with resume.

Why this exists
---------------
Docker's own registry client does NOT resume a layer download: when the
connection drops mid-layer it restarts that layer from zero ("short read ...
unexpected EOF"). On a link that stalls every few minutes this means the
265 MB layer can never complete, so ``kind create cluster`` can never pull its
node image.

This script fetches the exact same registry blobs, but with HTTP ``Range``
resume plus an unlimited retry loop, then assembles a classic
``docker save``-style archive that ``docker load`` accepts. Every byte is
verified against the size advertised in the manifest, so a truncated layer is
never accepted.

Usage (only needed when the node image is NOT already in Docker's cache):

    python infra/k8s/kind-node-image-pull.py
    docker load -i "%TEMP%\\kindnode-v1.37.0\\kindest-node-v1.37.0.tar"
    kind create cluster --config infra/k8s/kind-cluster.yaml --image kindest/node:v1.37.0

The ``--image`` flag matters: Docker Desktop's containerd image store re-digests
a ``docker load``ed image, so kind's default digest-pinned lookup
(``kindest/node:v1.37.0@sha256:...``) does not match it and kind would try to
pull. Naming the image explicitly makes kind use the local copy.
"""
import json
import os
import shutil
import sys
import tarfile
import time
import urllib.request

REPO = "kindest/node"
TAG = "v1.37.0"
OS_NAME = "linux"
ARCH = "amd64"

WORK = os.path.join(os.environ.get("TEMP") or ".", "kindnode-v1.37.0")
TARBALL = os.path.join(WORK, "kindest-node-v1.37.0.tar")
ACCEPT = ",".join([
    "application/vnd.oci.image.index.v1+json",
    "application/vnd.docker.distribution.manifest.list.v2+json",
    "application/vnd.docker.distribution.manifest.v2+json",
    "application/vnd.oci.image.manifest.v1+json",
])
CHUNK = 262_144
PROGRESS_EVERY = 8 * 1024 * 1024


def log(*args):
    print(*args, flush=True)


def token():
    """A fresh anonymous pull token (they expire after ~5 minutes)."""
    url = ("https://auth.docker.io/token?service=registry.docker.io"
           "&scope=repository:%s:pull" % REPO)
    last = None
    for _ in range(30):
        try:
            with urllib.request.urlopen(url, timeout=60) as resp:
                return json.load(resp)["token"]
        except Exception as exc:  # noqa: BLE001 - retry any transport failure
            last = exc
            time.sleep(3)
    raise SystemExit("could not obtain a registry token: %s" % last)


def get_json(path):
    req = urllib.request.Request("https://registry-1.docker.io/v2/%s%s" % (REPO, path))
    req.add_header("Authorization", "Bearer %s" % token())
    req.add_header("Accept", ACCEPT)
    with urllib.request.urlopen(req, timeout=60) as resp:
        return json.load(resp)


def fetch_blob(digest, dest, size):
    """Download one blob, resuming across drops until exactly `size` bytes."""
    if os.path.exists(dest):
        if os.path.getsize(dest) == size:
            log("  cached  %s" % os.path.basename(dest))
            return
        os.remove(dest)

    part = dest + ".part"
    if size == 0:
        open(dest, "wb").close()
        return

    attempt = 0
    since_log = 0
    while True:
        attempt += 1
        have = os.path.getsize(part) if os.path.exists(part) else 0
        if have == size:
            os.replace(part, dest)
            log("  done    %s (%d bytes, %d resume attempt(s))"
                % (os.path.basename(dest), size, attempt - 1))
            return
        if have > size:
            os.remove(part)
            have = 0

        try:
            req = urllib.request.Request(
                "https://registry-1.docker.io/v2/%s/blobs/%s" % (REPO, digest))
            req.add_header("Authorization", "Bearer %s" % token())
            if have:
                req.add_header("Range", "bytes=%d-" % have)
            with urllib.request.urlopen(req, timeout=120) as resp:
                if have and resp.status != 206:
                    log("  (server ignored Range - restarting layer)")
                    have = 0
                since_log = 0
                with open(part, "ab" if have else "wb") as fh:
                    while True:
                        block = resp.read(CHUNK)
                        if not block:
                            break
                        fh.write(block)
                        since_log += len(block)
                        if since_log >= PROGRESS_EVERY:
                            since_log = 0
                            log("  ...     %s  %d/%d MB"
                                % (os.path.basename(dest),
                                   os.path.getsize(part) // 1_048_576,
                                   size // 1_048_576))
            got = os.path.getsize(part)
            if got >= size:
                continue  # loop re-enters and renames to dest
            log("  short   %s stopped at %d/%d bytes" % (os.path.basename(dest), got, size))
        except Exception as exc:  # noqa: BLE001 - network drops are expected
            got = os.path.getsize(part) if os.path.exists(part) else 0
            log("  retry   %s at %d/%d bytes: %s"
                % (os.path.basename(dest), got, size, exc))
        time.sleep(2)


def main():
    os.makedirs(WORK, exist_ok=True)
    if os.path.exists(TARBALL):
        log("archive already present: %s" % TARBALL)
        return

    log("resolving %s:%s for %s/%s ..." % (REPO, TAG, OS_NAME, ARCH))
    manifest = get_json("/manifests/%s" % TAG)
    if "manifests" in manifest:
        entry = next(m for m in manifest["manifests"]
                     if m["platform"]["os"] == OS_NAME
                     and m["platform"]["architecture"] == ARCH)
        log("platform manifest: %s" % entry["digest"])
        manifest = get_json("/manifests/%s" % entry["digest"])

    config_desc = manifest["config"]
    layers = manifest["layers"]
    log("config  %s (%d bytes)" % (config_desc["digest"], config_desc["size"]))
    for idx, layer in enumerate(layers):
        log("layer %d %s (%d bytes)" % (idx, layer["digest"], layer["size"]))

    # ---- config blob -------------------------------------------------------
    cfg_path = os.path.join(WORK, config_desc["digest"].split(":")[1] + ".json")
    log("fetching config ...")
    fetch_blob(config_desc["digest"], cfg_path, config_desc["size"])
    with open(cfg_path, "r", encoding="utf-8") as fh:
        config = json.load(fh)
    diff_ids = config["rootfs"]["diff_ids"]
    if len(diff_ids) != len(layers):
        raise SystemExit("config has %d diff_ids for %d layers" % (len(diff_ids), len(layers)))

    # ---- layer blobs, decompressed to <diff_id>/layer.tar ------------------
    layer_paths = []
    for idx, (layer, diff_id) in enumerate(zip(layers, diff_ids)):
        hex_id = diff_id.split(":")[1]
        layer_dir = os.path.join(WORK, hex_id)
        os.makedirs(layer_dir, exist_ok=True)
        layer_tar = os.path.join(layer_dir, "layer.tar")
        if os.path.exists(layer_tar) and os.path.getsize(layer_tar) > 0:
            log("layer %d already extracted" % idx)
        else:
            blob = os.path.join(WORK, layer["digest"].split(":")[1] + ".blob")
            log("fetching layer %d ..." % idx)
            fetch_blob(layer["digest"], blob, layer["size"])
            log("extracting layer %d ..." % idx)
            import gzip
            with gzip.open(blob, "rb") as src, open(layer_tar, "wb") as dst:
                shutil.copyfileobj(src, dst, 1024 * 1024)
            os.remove(blob)
        layer_paths.append("%s/layer.tar" % hex_id)

    # ---- docker save manifest ---------------------------------------------
    save_manifest = [{
        "Config": os.path.basename(cfg_path),
        "RepoTags": ["%s:%s" % (REPO, TAG)],
        "Layers": layer_paths,
    }]
    manifest_out = os.path.join(WORK, "manifest.json")
    with open(manifest_out, "w", encoding="utf-8") as fh:
        json.dump(save_manifest, fh)

    # ---- tar it up ---------------------------------------------------------
    log("writing archive %s ..." % TARBALL)
    names = [os.path.basename(cfg_path)] + layer_paths + ["manifest.json"]
    with tarfile.open(TARBALL, "w") as tar:
        tar.add(manifest_out, arcname="manifest.json")
        tar.add(cfg_path, arcname=os.path.basename(cfg_path))
        for rel in layer_paths:
            tar.add(os.path.join(WORK, rel), arcname=rel)
    log("archive ready: %s (%d bytes)" % (TARBALL, os.path.getsize(TARBALL)))
    log("contents: %s" % ", ".join(names))


if __name__ == "__main__":
    main()
