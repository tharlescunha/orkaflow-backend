# app\core\exceptions.py

from fastapi import HTTPException, status


class OrkaFlowException(HTTPException):
    def __init__(self, status_code: int, detail: str):
        super().__init__(status_code=status_code, detail=detail)


class NotFoundException(OrkaFlowException):
    def __init__(self, detail: str = "Recurso não encontrado."):
        super().__init__(status.HTTP_404_NOT_FOUND, detail)


class ConflictException(OrkaFlowException):
    def __init__(self, detail: str = "Conflito de dados."):
        super().__init__(status.HTTP_409_CONFLICT, detail)


class ValidationException(OrkaFlowException):
    def __init__(self, detail: str = "Erro de validação."):
        super().__init__(status.HTTP_400_BAD_REQUEST, detail)


class UnauthorizedException(OrkaFlowException):
    def __init__(self, detail: str = "Não autenticado."):
        super().__init__(status.HTTP_401_UNAUTHORIZED, detail)


class ForbiddenException(OrkaFlowException):
    def __init__(self, detail: str = "Acesso negado."):
        super().__init__(status.HTTP_403_FORBIDDEN, detail)
        