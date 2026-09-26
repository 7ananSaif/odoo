# Odoo Invoice Agent: Automated Workflows, Cron Jobs, and Integrations

This document outlines the automated actions, scheduled cron jobs, and message broker outbox patterns used in the Invoice Agent module.

---

## 1. Automations & Maintenance (`automation_data.xml`)

### A. Server Action: Flag Low-Confidence Bill
* **Model:** `account.move`
* **Purpose:** Triggers when an AI extraction falls below the required confidence threshold.
* **Actions Performed:**
  * Logs a warning via `_logger`.
  * Posts a warning message directly into the document's chatter.
  * Sets `ai_review_required = True` if the extraction is still in the `extracted` state.

### B. Base Automation: AI Flag Low-Confidence Bills
* **Model:** `account.move`
* **Trigger:** `on_create_or_write`
* **Filter Domain:** `['!', ('ai_confidence', '>=', 0.8)]` (Fires when confidence is below 80%).
* **Action:** Executes the `server_action_flag_low_confidence` server action.

### C. Cron Job: Retry Stuck Extractions
* **Interval:** Every 30 minutes
* **Purpose:** Acts as a safety net to find bills stuck in processing states for over an hour and resets them back to `pending`.

---

## 2. OCR & Extraction Pipelines (`cron_jobs_data.xml`)

### A. Invoice Agent: OCR Pending Bills
* **Interval:** Every 2 minutes
* **Batch Size:** 10 records per tick
* **Purpose:** Claims pending records to run PDF rasterization and OCR processing safely off the web request thread, preventing HTTP worker locks and out-of-memory (OOM) issues.

### B. Invoice Agent: Extract Pending Bills
* **Interval:** Every 2 minutes
* **Batch Size:** 5 records per tick
* **Purpose:** Consumes OCR-finished bills (`ocr_state == done`), passes them to Claude for extraction and calibrated confidence scoring, and handles routing.

### C. Invoice Agent: Backfill Vendor-Doc Embeddings
* **Interval:** Every 10 minutes
* **Batch Size:** 100 records per tick
* **Purpose:** Backfills RAG vector embeddings for posted vendor bills (`ai_indexed == False`) to support semantic search and matching.

---

## 3. AMQP Integration Outbox (`cron_outbox_data.xml`)

### A. Invoice Agent: Drain AMQP Outbox
* **Interval:** Every 1 minute
* **Batch Size:** 50 rows per tick
* **Model:** `invoice.agent.job`
* **Purpose:** Publishes unsent transactional outbox rows to the `invoice.agent` message broker topic exchange as `extract.request` messages. 
* **Design Benefits:** 
  * Writes to the same cursor as the bill save to ensure transactional safety (a failed broker push never rolls back a user's bill save).
  * Automatically retries on subsequent ticks if the message broker is temporarily down.