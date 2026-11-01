from . import controllers, models, wizard
from .hooks import post_init_hook

# NOTE: this addon used to declare a ``post_load`` hook here, which started a
# daemon thread per Odoo process to consume results from the ``invoice.result``
# AMQP queue. Results now arrive over HTTP at ``POST /invoice_agent/result``
# (``controllers/main.py``) and are applied by
# ``models/result_service.py`` — see the review's P1-3 and Wave 3. There is
# therefore nothing to start at load time: an HTTP route holds no thread, no
# broker connection and no hand-built environment between calls.
