from typing import Annotated

from fastapi import Header


def version(
    version: Annotated[
        str | None,
        Header(
            alias="Version",
            description="TODO",
        ),
    ] = None,
) -> str:
    return version or "1.0"
