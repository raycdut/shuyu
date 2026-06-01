"""Persistence — legacy-compatibility re-exports from configdb.

The ``init_sqlite()`` function previously called here has been moved to
:func:`app.configdb.init_configdb`.  Prompt defaults are re-exported
from ``app.configdb`` for backward compatibility with old imports.
"""

from __future__ import annotations

import logging

from ..configdb import (
    DEFAULT_PROMPT,
    SQL_GEN_PROMPT,
    PLAN_PROMPT,
    PLAN_REFLECT_PROMPT,
    REPORT_REFLECT_PROMPT,
    SCHEMA_DESCRIBE_PROMPT,
    FREEFORM_EXEC_PROMPT,
    REPORT_GEN_PROMPT,
    REPORT_SUPPLEMENT_PROMPT,
    REPORT_REGEN_PROMPT,
    PROMPT_DEFAULTS,
    _get_default_prompt_content,
)

logger = logging.getLogger("shuyu.main")

__all__ = [
    "DEFAULT_PROMPT",
    "SQL_GEN_PROMPT",
    "PLAN_PROMPT",
    "PLAN_REFLECT_PROMPT",
    "REPORT_REFLECT_PROMPT",
    "SCHEMA_DESCRIBE_PROMPT",
    "FREEFORM_EXEC_PROMPT",
    "REPORT_GEN_PROMPT",
    "REPORT_SUPPLEMENT_PROMPT",
    "REPORT_REGEN_PROMPT",
    "PROMPT_DEFAULTS",
    "_get_default_prompt_content",
]
