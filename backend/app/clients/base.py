from abc import ABC, abstractmethod
from app.models.manuals import SearchManualResponse

class ManualClientBase(ABC):
    @abstractmethod
    async def search(self, query: str, machine_id: str)->SearchManualResponse:
        pass