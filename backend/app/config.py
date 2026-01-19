import os
from pathlib import Path

# Base data directory (can be overridden with env var WOUNDSYNC_BASE_DATA_DIR)
DEFAULT_BASE_DATA_DIR = Path.cwd() / "WoundSync Model Stuff"
BASE_DATA_DIR = Path(os.getenv("WOUNDSYNC_BASE_DATA_DIR", str(DEFAULT_BASE_DATA_DIR)))
BASE_DATA_DIR.mkdir(parents=True, exist_ok=True)

# Visual results directory (can be overridden with env var WOUNDSYNC_OUTPUT_DIR)
DEFAULT_BASE_OUTPUT_DIR = Path.cwd() / "backend" / "output"
BASE_OUTPUT_DIR = Path(os.getenv("WOUNDSYNC_OUTPUT_DIR", str(DEFAULT_BASE_OUTPUT_DIR)))
BASE_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_base_output_dir() -> str:
	"""Return the base directory for saving visual outputs as a string path."""
	return str(BASE_OUTPUT_DIR)

# Roboflow (optional cloud model) configuration via env vars
# - ROBOFLOW_API_KEY: your Roboflow API key
# - ROBOFLOW_MODEL_ID: e.g., "your-workspace/your-model/1"
# - ROBOFLOW_API_URL: override for self-hosted endpoint, defaults to serverless.roboflow.com
ROBOFLOW_API_KEY = os.getenv("ROBOFLOW_API_KEY")
ROBOFLOW_MODEL_ID = os.getenv("ROBOFLOW_MODEL_ID")
ROBOFLOW_API_URL = os.getenv("ROBOFLOW_API_URL", "https://serverless.roboflow.com")

def get_roboflow_config() -> dict:
	return {
		"api_key": ROBOFLOW_API_KEY,
		"model_id": ROBOFLOW_MODEL_ID,
		"api_url": ROBOFLOW_API_URL,
	}

