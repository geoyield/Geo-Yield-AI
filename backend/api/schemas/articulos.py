from pydantic import BaseModel, ConfigDict


class ArticuloOut(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fuente_legal: str
    numero_articulo: str
    titulo: str
    contenido: str