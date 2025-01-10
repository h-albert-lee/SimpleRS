from abc import ABC, abstractmethod
from typing import Any, List

class BaseModel(ABC):
    @abstractmethod
    def train(self, data: Any) -> None:
        pass

    @abstractmethod
    def predict(self, user_id: str, candidates: List[Any]) -> List[Any]:
        pass

    @abstractmethod
    def save(self, path: str) -> None:
        pass

    @abstractmethod
    def load(self, path: str) -> None:
        pass
