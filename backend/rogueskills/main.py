import uvicorn

from .api.app import create_app
from .settings import settings

app = create_app(settings)


def run() -> None:
    uvicorn.run("rogueskills.main:app", host=settings.host, port=settings.port, reload=False)


if __name__ == "__main__":
    run()
