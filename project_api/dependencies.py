from fastapi import Header
from typing import Annotated

def version(
    version: Annotated[str | None,
    Header(alias="Version",
          description="TODO",)] = None,
            ) -> str:
    return version or "1.0"
