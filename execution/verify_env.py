import os
from dotenv import load_dotenv

# Check BEFORE loading .env (system env)
sys_key = os.environ.get("OPENAI_API_KEY", "Not Set")
print(f"System Env Key Start: {sys_key[:10] if sys_key else 'None'}")

# Load .env
load_dotenv(override=True)
loaded_key = os.environ.get("OPENAI_API_KEY", "Not Set")
print(f"Loaded .env Key Start: {loaded_key[:10] if loaded_key else 'None'}")

# Check value length
print(f"Key Length: {len(loaded_key) if loaded_key else 0}")
