import re


def only_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def is_valid_cpf(digits: str) -> bool:
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for i in (9, 10):
        total = sum(int(digits[n]) * (i + 1 - n) for n in range(i))
        if (total * 10) % 11 % 10 != int(digits[i]):
            return False
    return True


def _cnpj_check_digit(base: str, weights: list[int]) -> int:
    remainder = sum(int(d) * w for d, w in zip(base, weights, strict=True)) % 11
    return 0 if remainder < 2 else 11 - remainder


def is_valid_cnpj(digits: str) -> bool:
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    first = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    second = [6, *first]
    return _cnpj_check_digit(digits[:12], first) == int(digits[12]) and _cnpj_check_digit(
        digits[:13], second
    ) == int(digits[13])


def normalize_document(value: str) -> str:
    """Valida CPF/CNPJ e devolve somente os dígitos."""
    digits = only_digits(value)
    if len(digits) == 11 and is_valid_cpf(digits):
        return digits
    if len(digits) == 14 and is_valid_cnpj(digits):
        return digits
    raise ValueError("CPF ou CNPJ inválido")
