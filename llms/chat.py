from langchain_ollama import ChatOllama, OllamaEmbeddings
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_community.vectorstores import Chroma
from sentence_transformers import SentenceTransformer
import json
import os 
import shutil



class OllamaChat:
    def __init__(self, 
                 model: str = "llama3"):
        self.llm = ChatOllama(model=model)
        self.prompt = ChatPromptTemplate.from_messages([
            ("system", """Eres un asesor comercial experto de Procesadora Ecograsas.
        Solo puedes recomendar estos productos:
        {productos}

        Adapta tu estilo según la pregunta del cliente. 
        No uses estructuras repetitivas ni saludos fijos. 
        Responde máximo en 100 palabras."""),
            ("user", "{input}")
            
        ])
        self.rag = ProductRAG()

    def chat_response(self, message: str) -> str:
        #messages = [
        #    SystemMessage(content=self.system_prompt),
        #    HumanMessage(content=message)
        #        ]
        contexto = self.rag.buscar(message)
        contexto_text = "\n".join(doc.page_content for doc in contexto)
        chain = self.prompt | self.llm
        #response = self.llm.invoke(messages)
        response = chain.invoke({"input": message, "productos": contexto_text})
        return response.content


class ProductRAG:
    def __init__(self, catalog_path="llms/productos.json", persist_dir="db"):
        self.embeddings = OllamaEmbeddings(model="nomic-embed-text")  # embeddings locales
        self.persist_dir = persist_dir

        with open(catalog_path, "r", encoding="utf-8") as f:
            self.catalog = json.load(f)
        # Regenerar BD vectorial siempre que se inicie
        if os.path.exists(persist_dir):
            shutil.rmtree(persist_dir)
        # Convertir productos en textos para indexar
        docs = []
        metadatas = []

        for p in self.catalog:
            texto = f"""
            Nombre: {p['nombre']}
            Presentación: {p['presentacion']}
            Uso: {p['uso']}
            Industria: {p['industria']}
            Características: {p['caracteristicas']}
            """
            docs.append(texto)
            metadatas.append({"id": p["id"], "nombre": p["nombre"]})

        # Construir o cargar BD de vectores
        self.db = Chroma.from_texts(
            docs,
            embedding=self.embeddings,
            metadatas=metadatas,
            persist_directory=None
        )

    def buscar(self, query: str, k: int = 2):
        """Busca los productos más similares al mensaje del cliente"""
        resultados = self.db.similarity_search(query, k=k)
        return resultados
# Uso
#llm = OllamaChat()
#print(llm.chat_response("Hola, recomiendame una manteca para hacer galletas."))
