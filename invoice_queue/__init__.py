"""Invoice Agent queue topology package.

``topology.py`` declares the RabbitMQ 0-9-1 topology the invoice agent uses:
the durable ``invoice.agent`` topic exchange, the ``invoice.extract`` queue
bound on ``extract.request``, the TTL-backed retry tiers and the
``invoice.extract.dead`` poison queue.

There is no ``invoice.result`` queue any more. Results travel the other way —
the worker POSTs a signed JWT to Odoo's ``/invoice_agent/result`` endpoint
(Wave 3, review finding P1-3), so only the *request* direction uses AMQP. A
broker provisioned before that change still holds the old queue and its
bindings; ``topology.delete_result_queue()`` removes them, on purpose by hand
rather than automatically.

Run against the local broker with ``python -m invoice_queue.topology`` or with a
plain ``python invoice_queue/topology.py`` — both work because the module reads the
broker connection from the same environment variables ``docker-compose``
injects (``RABBITMQ_USER`` / ``RABBITMQ_PASS`` / ``RABBITMQ_HOST``).
"""
