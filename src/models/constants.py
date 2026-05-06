from typing import Literal

FunctionalType = Literal["home", "form", "navigation", "dynamic", "informational"]
SelectionMode = Literal["directed", "random"]
MANDATORY_TYPES: frozenset = frozenset({"home", "form", "navigation"})
