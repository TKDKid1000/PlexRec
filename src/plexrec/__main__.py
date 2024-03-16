import uvicorn
from dotenv import load_dotenv

load_dotenv(override=True)

from .config import config

if __name__ == "__main__":
    uvicorn.run(
        app=f"{__package__}.app:app",
        host=config["server"]["host"],
        port=config["server"]["port"],
        reload=True,
    )
