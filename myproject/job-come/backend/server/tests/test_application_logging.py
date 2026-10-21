"""Metadata INFO logs must reach stdout; structlog configuration alone cannot do it."""
import json
import logging

import pytest

from jc.observability.logging_setup import configure_application_logging


@pytest.mark.parametrize("json_logs", [True, False])
def test_application_info_is_visible_and_configuration_is_idempotent(capsys, json_logs):
    namespace = logging.getLogger("jc")
    handlers, level, propagate = namespace.handlers[:], namespace.level, namespace.propagate
    try:
        namespace.handlers = []
        configure_application_logging(json_logs=json_logs, level="INFO")
        configure_application_logging(json_logs=json_logs, level="INFO")
        logging.getLogger("jc.services.preview_progress").info("preview_cache reason=hit")
        out = capsys.readouterr().out
        assert out.count("preview_cache reason=hit") == 1
        if json_logs:
            record = json.loads(out)
            assert record["level"] == "info"
            assert record["logger"] == "jc.services.preview_progress"
    finally:
        namespace.handlers, namespace.level, namespace.propagate = handlers, level, propagate
