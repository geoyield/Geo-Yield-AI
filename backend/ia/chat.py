
""""
Se constuye un agente en el que un LLM procesa el prompt de usuario, desgranando las tareas que se piden, llamando a herramientas para completarlas y finalmente, cuando considera que dispone de toda la información, componer una respuesta para el usuario. Se trata de una arquitectura ReAct (Reasoning and Acting: https://www.ibm.com/think/topics/react-agent)

Es un agente con memoria para cada usuario, que puede escoger si seguir con una conversación previa o inicar una nueva. En el notebook cada usuario se identifica con un thread_id
En este momento el agente dispone de dos herramientas:
- el modelo que infiere los mejores lugares para ubicar un negocio de hostelería dadas una serie de características (zona, perfil de cliente, características del servicio ofrecido, etc). Ofrece un iterfaz tipo API al modelo. Dado que es solamente una aplicación ad-hoc, no se considera el uso de MCP
- un RAG que da contexto sobre cuestiones de normativa y procedimientos 

Se usa el framework LangChain/LangGraph en tanto que provee unos esquemas estándar que se consideran particularmente útiles a la hora de introducirse en este mundo, empezar por genérico para poder evolucionar a lo particualar de un proveedor o tecnología, de ser necesario

La principal característica del modelo que soporta el agente que decide si se debe usar una tool y cuál y en qué punto dispone de toda la información para poder finalizar, es la de 'razonamiento'.
No se ha hecho porqué con el usuario genérico del PJ (geoyield@gmail.com)m no es posible crear cuenta en Google AI Studio. Es por ello que se usa usa groq: https://pricepertoken.com/endpoints/groq/free

El agente se plantea con memoria durante la interacción, de forma que las respuestas previas se añaden al contexto. Cada conversación dispone de un identificador, por lo que se puede retomar más tarde. Para evitar un crecimiento desmesurado del contexto, los mensajes más antiguos se se se van añadiendo a un mensaje de resumen en la base de la lista. 

Una vez comporbado el funcionamiento, se va a persistir en potgis la conversaciones de los usuarios (https://docs.langchain.com/oss/python/langgraph/add-memory#example-using-postgres-checkpointer)
"""

from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import MessagesState
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, ToolMessage, RemoveMessage
from pydantic import BaseModel
import requests
import json

from dotenv import load_dotenv

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import sys
from pathlib import Path

import logging

sys.path.insert(0, '/home/claud/pontia/PJ')

from backend.db.connection import resolve_database_url
from backend.rag.query_engine import retrieve_relevant_chunks, retrieve_relevant_chunks_with_rerank, build_context
from backend.rag.embeddings import embed_texts
         
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from backend.geo.geocoding import geocodificar_direccion

from langgraph.graph import StateGraph, START, END
from langgraph.prebuilt  import tools_condition, ToolNode
from langgraph.checkpoint.postgres import PostgresSaver
from IPython.display import Image, display 
from typing import Literal

#### CONFIGURACIÓN
logger = logging.getLogger("geoyield_agent")

load_dotenv()

GENERATION_MODEL = os.environ.get("GENERATION_MODEL", "models/gemini-3.6-flash")
MAX_NUM_MESSAGES = int(os.environ.get("MAX_NUM_MESSAGES", 5))
NUM_MESSGES_TO_SUMMARIZE = int(os.environ.get("NUM_MESSGES_TO_SUMMARIZE", 3))

GEODATA_BASEURL = resolve_database_url()

engine = create_engine(resolve_database_url())

#### STATE VARIABLE
# La clase predefinida MessageState contiene una lista de mensajes bajo la key 'messages' y el reducer 'add_messages' que añade un mensaje al final de la cola, usado 
# por langChain para operar con la salida de un nodo (añade el mensaje de salida a lista)
# cada mensaje tiene un campo 'id'. Si se añade un mensaje on un id ya existente, se reescribe el mensaje. Un mensaje se puede borrar de la lisa con
# 'RemoveMessasge(id)'

# se deriva la clase MessageState para introducir la key summary, que contiene un resumen de mensajes. Se usa para poder matener el contexto sin aumentar
# demasiado el númeoro de tokens

class State(MessagesState):
    summary: str

#### TOOLS DEFINITION
def get_opportunity_score(dirección: str) -> float:
    """
    devuelve un score para una dirección en la ciudad de Barcelona
    llama a la función geocodfican_direccion, que devuelve el código de distrito, entre otros datos y con ello
    se ejecuta la vista en 'district_scorecard' para retornar un opportunity_score

    Args:
        un string representando un dirección en la ciudad de Barcelona

    Returns:
        un float con el score (valor entre 0 y 1) o None si no se puede procesar
    """
    res = geocodificar_direccion(dirección)
    if res != None:
        with Session(engine) as session:
            row = session.execute(
                text(
                    "SELECT codi_districte, nom_districte, renta_media, daily_foot_traffic, "
                    "total_competitors, opportunity_score "
                    "FROM district_scorecard WHERE codi_districte = :codi"
                ),
                {"codi": res['codi_districte']},
            ).mappings().first()

        if row is None:
            logger.warning(
                "No hay datos en district_scorecard para el distrito %s",
                res['codi_districte']
            )
            return {"datos_distrito": None}

        return {"datos_distrito": dict(row)}

def regulations_query(query: str) -> str:
    """
    RAG que proporciona información sobre aspectos regulatorios y legales.

    Args:
        query (str): Consulta en lenguaje natural.

    """
    documents = []  
    with Session(engine) as session:
        documents = retrieve_relevant_chunks_with_rerank(session=session, query=query)
    return build_context(documents)

def summarize_conversation(state: State):
    if len(state['messages']) > MAX_NUM_MESSAGES:
        summary = state.get("summary", "")
        if summary:
            summary_message = (
                f"Este es el resumen de la conversación hasta ahora: {summary}\n\n"
                "Extiende el resumen teniendo en cuenta los mensajes anteriores:"
            )
        else:
            summary_message = "Crea un resumen teniendo en cuenta los mensajes anteriores:"

        # el modelo, sin tools, es llamado para generar el resumen
        messages = state["messages"] + [HumanMessage(content=summary_message)]
        response = llm.invoke(messages)
        
        # Delete all but the 2 most recent messages
        num_messages_left = len(state['messages']) - NUM_MESSGES_TO_SUMMARIZE
        delete_messages = [RemoveMessage(id=m.id) for m in state["messages"][:-num_messages_left]]
        return {"summary": response.content, "messages": delete_messages}

#### TOOL BINDING
# se ligan las tools que el modelo razona sobre si debe usar para obtener información
# summarize_conversation se dispara de forma determinista mediante un 'router' en función del número de mensajes el contexto
tools = [get_opportunity_score, regulations_query]
llm = ChatGoogleGenerativeAI(
    model=GENERATION_MODEL,
    temperature=0,
    max_retries=3,
 )
llm_with_tools = llm.bind_tools(tools)

#### ASSISTANT
sys_msg = SystemMessage(
    content="""Eres un asistente experto en hostelería y restauración, especializado en la ciudad de Barcelona. 
    Tu tarea es proporcionar información sobre aspectos regulatorios y legales relacionados con la apertura de negocios en esta ciudad y un opportunity_score
    Dispones de dos herramientas para ayudarte en tu tarea:
    1. get_opprotunity_score: devuelve un score a partir de una dirección en la ciudad de Barcelona.
    2. regulations_query: Esta herramienta te permite obtener información sobre aspectos regulatorios y legales relacionados con la apertura de negocios en Barcelona.
    Empieza la respuesta 'Dirección: [la dirección entrada en get_opportunity_score], score: [valor devuelto por get_opprotunity_score]
    Cuando respondas a las consultas de los usuarios, asegúrate de proporcionar información precisa y relevante, y de citar las fuentes de información cuando sea posible.
    Si no puedes encontrar información relevante, informa al usuario de que no se encontró información relevante.""")

def assistant(state: State):
    """
    Función principal del asistente, que recibe un estado de mensajes y devuelve una respuesta generada por el modelo de lenguaje.

    Args:
        state (MessagesState): Estado de mensajes que contiene la conversación actual.
        max_num_num_messages: cuando se supera este número de mensajes en state['messages'] los primeros se sustituyen por un resumen
        num_messages_to_summarize: se resumen los primeros 'num_messages_to_summarize'; debe ser menor que 'max_num_messages'
    """

    summary = state.get("summary", "")
    if summary:
        system_message = f"Resumen de la conversación previa: {summary}"
        messages = [SystemMessage(content=system_message)] + state["messages"]
    else:
        messages = state["messages"]

    return {'messages': [llm_with_tools.invoke([sys_msg] + messages)]}


#### CREATE AND COMPILE GRAPH WITH MEMORY
# router que decide si se debe crear un resumen antes de ir al final
def summarize_check(state: State)-> Literal ["summarize_conversation",END]:
    """Retorna si el próximo nodo es END o summarize_conversation"""
    
    if len(state["messages"]) > MAX_NUM_MESSAGES:
        return "summarize_conversation"
    return END

# Memoria persistente en PostgreSQL
checkpointer_context = PostgresSaver.from_conn_string(resolve_database_url())
checkpointer = checkpointer_context.__enter__()
checkpointer.setup()

# Grafo
builder = StateGraph(MessagesState)

# Definición de los nodos
builder.add_node("assistant", assistant)
builder.add_node("tools", ToolNode(tools))
builder.add_node('summarize', summarize_conversation)

# Definición de los conectores (edges) entre nodos
builder.add_edge(START, "assistant")
# este conector enruta a las tools si el último mensaje de assistant es un tool call o en dirección al final en otro caso
builder.add_conditional_edges(
    "assistant",
    tools_condition,
    {'tools': 'tools', '__end__': 'summarize'}
)
builder.add_edge('tools', 'assistant')
builder.add_edge('summarize', END)
react_graph = builder.compile(checkpointer=checkpointer)

#### FUNCIÓN DE LLAMADA AL ASISTENTE
def request(content: str, thread: str) -> str:
    """"
    Entra la última petición del usuario en el hilo de conversación den el chat al asistente y devuleve respuesta
    
    Args:
        content: texto de la petición
        thread: identificador del hilo de conversación

    Returns:
        un texto con la respuesta del asistente
    """
    messages = [{
    'role': 'user',
    'content': {content}
    }]
    configurable = {'thread_id': thread}

    state = react_graph.invoke(
        {'messages': messages},
        {'configurable': configurable}
    )

    return state['messages'][-1]

if __name__ == '__main__':
    print("para persistir la conversación me deberías dar tu usuario\nusuario:")
    print("quieres seguir alguna de estas conversacines o iniciar una nueva?")

    request(sys.argv[1], sys.argv[2]).text
    