from pathlib import Path
from data.excel_provider import ExcelDataProvider
from data.models import RegistrationResult, RegistrationStatus


def test_excel_provider_reads_test_xlsx():
    test_file = Path("Test.xlsx")
    if not test_file.exists():
        return

    provider = ExcelDataProvider(file_path=test_file)
    all_clients = provider.get_all_clients()
    assert len(all_clients) > 0

    valid_clients = provider.get_valid_clients()
    assert len(valid_clients) > 0

    first = valid_clients[0]
    assert first.first_name != ""
    assert "@" in first.email
    assert len(first.phone) >= 10
    assert first.phone.startswith("0")
