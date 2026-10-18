from typing import Annotated

from pydantic import AfterValidator, EmailStr, StringConstraints


def _check_password_strength(value: str) -> str:
    if not any(c.isalpha() for c in value) or not any(c.isdigit() for c in value):
        raise ValueError("A senha deve conter letras e números")
    return value


PasswordStr = Annotated[
    str,
    StringConstraints(min_length=10, max_length=128),
    AfterValidator(_check_password_strength),
]

NormalizedEmail = Annotated[EmailStr, AfterValidator(str.lower)]

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=160)]

PersonName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=2, max_length=120)]
