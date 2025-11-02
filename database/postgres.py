from sqlmodel import SQLModel, create_engine, Session
from decouple import config
from models.pedidos import Pedidos, Pedido_Detalle

engine = create_engine(config('Postgres'),echo=True)
def create_tables_and_db():
    try:
        print(engine)
        SQLModel.metadata.create_all(engine)
    except Exception as e:
        print(e)     

def get_session():
    with Session(engine) as session:
        yield session
            