class OrkaFlowException(Exception):
    """
    Exceção base do projeto.

    Todas as exceções customizadas devem herdar desta classe.
    """

    def __init__(self, message: str = "Ocorreu um erro na aplicação."):
        self.message = message
        super().__init__(self.message)


class BusinessRuleException(OrkaFlowException):
    """
    Erro de regra de negócio.
    """
    pass


class NotFoundException(OrkaFlowException):
    """
    Erro para recurso não encontrado.
    """
    pass


class UnauthorizedException(OrkaFlowException):
    """
    Erro para acesso não autorizado.
    """
    pass


class ValidationException(OrkaFlowException):
    """
    Erro para validações de domínio.
    """
    pass


class DatabaseException(OrkaFlowException):
    """
    Erro relacionado a banco de dados.
    """
    pass
