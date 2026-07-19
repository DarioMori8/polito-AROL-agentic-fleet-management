from abc import ABC, abstractmethod
from contracts import SearchManualResponse

class ManualClientBase(ABC):
    @abstractmethod
    async def search(self, query: str, machine_id: str)->SearchManualResponse:
        pass