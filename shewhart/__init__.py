"""shewhart — statistical process control for Python.

Validated, pandas-native, automation-first SPC: control charts, process
capability, and measurement systems analysis.

This is an early name-holding release with first working primitives.
See https://github.com/bertanucar/shewhart for the roadmap.
"""

from shewhart.charts import beyond_limits, imr_limits

__version__ = "0.0.1"
__all__ = ["imr_limits", "beyond_limits", "__version__"]
