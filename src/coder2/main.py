import logging

from workflow.Workflow import get_app

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Create and invoke the workflow app
# ---------------------------------------------------------------------------
app = get_app()

print("Starting coding workflow...\n")
result = app.invoke({})

print("\n# ========================================================== #")
print("Final results")
print("# ========================================================== #")
print(result)
