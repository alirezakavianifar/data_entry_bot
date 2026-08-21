from abc import ABC, abstractmethod
from typing import List
from data.models import Client, RegistrationResult


class BaseDataProvider(ABC):
    """Abstract interface for data providers (Excel & Google Sheets)."""

    @abstractmethod
    def get_all_clients(self) -> List[Client]:
        """Loads and normalizes all client records from the data source."""
        pass

    def get_valid_clients(self) -> List[Client]:
        """Returns only clients with valid required fields for signup."""
        all_clients = self.get_all_clients()
        valid_clients = []
        for client in all_clients:
            is_valid, _ = client.is_valid_for_signup
            if is_valid:
                valid_clients.append(client)
        return valid_clients

    @abstractmethod
    def record_success(self, result: RegistrationResult) -> bool:
        """Records a successful account registration into the results destination."""
        pass

    @abstractmethod
    def record_failure(self, result: RegistrationResult) -> bool:
        """Optionally logs failure notes or status in the results destination."""
        pass
