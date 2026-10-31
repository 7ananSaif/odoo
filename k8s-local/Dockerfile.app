# =============================================================================
# Dockerfile.app — the image the local cluster runs.
#
# WHY A THIN LAYER OVER THE REPO'S OWN DOCKERFILE
# -----------------------------------------------
# The repo's ./Dockerfile builds the real application image: odoo:19 base, plus
# tesseract/ghostscript/poppler, plus custom_addons/invoice_agent/requirements.txt
# (anthropic, pytesseract, pdf2image, boto3, PyJWT, pika, redis). That image is
# what runs in production, so the local cluster must run it too — re-creating a
# different image here would make "works locally" meaningless.
#
# The one thing it does NOT contain is the addons themselves: docker-compose.yml
# bind-mounts ./custom_addons at /mnt/extra-addons for live development, and the
# Dockerfile deliberately does not COPY it (double-copying the whole repo into a
# 6.6 GB image caused "no space left on device" on small instances).
#
# A bind mount is not available inside a cluster, so this layer adds exactly the
# directory that was being bind-mounted - nothing else changes. The addons path
# (/opt/odoo/addons,/mnt/extra-addons) then matches docker/odoo.conf verbatim.
#
# BUILD (from the repo root, so custom_addons is in the context):
#   docker build -t odoo-invoice-agent:local .                  # repo Dockerfile
#   docker build -f k8s-local/Dockerfile.app \
#                -t odoo-local:19 .                             # this file
# `make image` in k8s-local/ does both.
#
# BASE_IMAGE is an ARG so you can point it at a different tag (e.g. a
# registry-pushed build) without editing the file.
# =============================================================================
ARG BASE_IMAGE=odoo-invoice-agent:local
FROM ${BASE_IMAGE}

# COPY requires root to write into /mnt (owned by root in the base image), then
# drop back to the unprivileged odoo user exactly as ./Dockerfile finishes.
USER root

# Trailing slash matters: copy the *contents* of custom_addons into
# /mnt/extra-addons, which is the directory odoo.conf lists on addons_path.
COPY custom_addons/ /mnt/extra-addons/

# The volume Odoo writes its filestore into is a PVC mounted here at runtime.
# Creating it in the image (owned by odoo) means a fresh volume whose root is
# not yet chgrp'd still has a usable mount point.
RUN mkdir -p /var/lib/odoo/filestore && chown -R odoo:odoo /var/lib/odoo

USER odoo
