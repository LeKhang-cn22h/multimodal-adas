"""Root entry point — runs the FastAPI app via uvicorn."""

import os
import uvicorn

if __name__ == "__main__":
    port = int(os.getenv("PORT", "8007"))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)
