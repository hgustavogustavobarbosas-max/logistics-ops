import pytest

from app.core.documents import is_valid_cnpj, is_valid_cpf, normalize_document


def test_valid_documents_are_normalized_to_digits() -> None:
    assert normalize_document("529.982.247-25") == "52998224725"
    assert normalize_document("11.222.333/0001-81") == "11222333000181"


@pytest.mark.parametrize("value", ["123", "52998224724", "11111111111", "11222333000182", ""])
def test_invalid_documents_are_rejected(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_document(value)


def test_validators_check_digits() -> None:
    assert is_valid_cpf("52998224725") and not is_valid_cpf("52998224726")
    assert is_valid_cnpj("11444777000161") and not is_valid_cnpj("11444777000160")
