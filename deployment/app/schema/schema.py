from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone
import logging
import os

logger = logging.getLogger("geoyield_api")

#####################
## MODELO DE DATOS ##
#####################

# El modelo de datos se define utilizando Pydantic, lo que permite validar los datos de entrada y salida de la API de manera sencilla y eficiente.

# Lo que se muestra abajo es solamente a modo de plantilla, para tener una idea inicial de como desplegarlo
# cuando se disponga de la arquitectura a alto nivel de la aplicación, lo que inluye los enpoints básicos, se va a definir

class TaskCreate(BaseModel):
    titulo: str = Field(min_length=1, description="Título de la tarea")
    contenido: str = Field(min_length=1, description="Contenido de la tarea")
    deadline: datetime = Field(description="Fecha de vencimiento")

    @field_validator('deadline')
    def deadline_check(cls, value):
        if value <= datetime.now(timezone.utc):
            raise ValueError('deadline debe estar en el futuro')
        return value

class TaskUpdate(BaseModel):
    completada: bool = Field(description="Estado de completado")

class TaskDelete(BaseModel):
    borrada: bool = Field(description="Tarea borrada")

class TaskResponse(BaseModel):
    id: int
    titulo: str
    contenido: str
    deadline: datetime
    completada: bool
    fecha_creacion: datetime
