from enum import Enum

class CandidateSource(Enum):
    """Enum for different candidate source pools."""
    GLOBAL = "global"
    LOCAL = "local"
    OTHER = "other"

