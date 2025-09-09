import pyodbc
from decouple import config
from datetime import datetime
from pydbisam import PyDBISAM

class DBISAMDatabase:
    def __init__(self):
        self.dsn = config('DSN')
        self.catalog = config('CatalogName')
        print('INIT', self.catalog, self.dsn)
        #self.tmp_table_tasks = settings.DBISAM_DATABASE['TMP_TABLE_TASKS']

    def connect_dbisam(self):
        conn = pyodbc.connect(f'DSN={self.dsn};CatalogName={self.catalog}')
        return conn
    
    def a2invcostosprecios(self):
        try: 
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    cursor.execute("""SELECT FI_CODIGO, 
                                     CASE WHEN FIC_IMP01ACTIVO = 1 THEN ROUND(FIC_P01PRECIOTOTALEXT * 1.16,2)
                                          WHEN FIC_IMP02ACTIVO = 1 THEN ROUND(FIC_P01PRECIOTOTALEXT * 1.08,2)
                                     ELSE FIC_P01PRECIOTOTALEXT
                                     END AS PRECIO 
                                     INTO PRECIOS
                                     FROM SINVENTARIO
                                     INNER JOIN A2INVCOSTOSPRECIOS ON FIC_CODEITEM = FI_CODIGO
                                     WHERE FI_STATUS = 1 """)
            precios = {}        
            with PyDBISAM(self.catalog +'\\PRECIOS.dat') as db:
                for row in db.rows():
                    precios[row[0]] = [row[1]]  
                #print(row)  
            return precios  
        except Exception as e:
            return str(e)
                   
    def consultar_precios(self, productos: list[str], tipo_precio: str):
        try:
            precios = {'P1': 'P01', 'P2': 'P02', 'P3': 'P03'}
            parse_products = '(' +  ','.join(map(lambda x: f"'{x}'", productos)) + ')' 
            print(parse_products)
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    productos=cursor.execute(f"""SELECT FI_CODIGO, FI_DESCRIPCION, 
                                     CASE WHEN FIC_IMP01ACTIVO = 1 THEN ROUND(FIC_{precios[tipo_precio] if tipo_precio in precios.keys() else 'P01'}PRECIOTOTALEXT * 1.16,2)
                                          WHEN FIC_IMP02ACTIVO = 1 THEN ROUND(FIC_{precios[tipo_precio] if tipo_precio in precios.keys() else 'P01'}PRECIOTOTALEXT * 1.08,2)
                                     ELSE FIC_P01PRECIOTOTALEXT
                                     END AS PRECIO 
                                     FROM SINVENTARIO
                                     INNER JOIN A2INVCOSTOSPRECIOS ON FIC_CODEITEM = FI_CODIGO
                                     WHERE FI_STATUS = 1 AND FI_CODIGO IN {parse_products}""").fetchall()
                    print(productos)
        except Exception as e:
            print(str(e))
            return str(e)   

    async def insert_pedidos(self, pedido):
        async with await self.connect() as conn:
            async with await conn.cursor() as cursor:
                await cursor.execute("""INSERT INTO SOPERACIONINV (PEDIDO, CLIENTE, FECHA, TOTAL)
                                        VALUES (?, ?, ?, ?)""",
                                        pedido['pedido'], pedido['cliente'], pedido['fecha'], pedido['total'])
                await conn.commit()      

    def create_table_tmp(self, name_table):
        conn = self.connect()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS "%s\\TMPDJANGO%s" ("SKU" VARCHAR(50), "PRECIO" FLOAT)
        """% (self.tmp_table_tasks, name_table))

    def insert_data_tmp(self, sku, precio, name_table):
        conn = self.connect()
        cursor  =  conn.cursor()
        cursor.execute("""INSERT INTO "%s\\TMPDJANGO%s" (SKU, PRECIO) VALUES ('%s', %s)""" % (self.tmp_table_tasks, name_table, sku, precio)  )
        conn.commit()
    
    def update_a2precios(self, name_table):
        conn = self.connect()
        cursor  =  conn.cursor()
        row_count = cursor.execute("""UPDATE A2INVCOSTOSPRECIOS SET FIC_P01PRECIOTOTALEXT = PRECIO
                          FROM A2INVCOSTOSPRECIOS
                          INNER JOIN "%s\\TMPDJANGO%s" ON SKU = FIC_CODEITEM 
                         WHERE FIC_CODEITEM NOT IN (SELECT FO_PRODUCTO FROM SINVOFERTA WHERE ('%s' BETWEEN FO_FECHAINICIO AND FO_FECHAFINAL) AND FO_VISIBLE = 1 ) """ 
                       % (self.tmp_table_tasks, name_table, datetime.now().strftime('%Y-%m-%d')))
        print(f"Rows updated: {row_count.rowcount}")
        conn.commit()
        

        def delete_table(self, name_table):
            conn = self.connect()
            cursor  =  conn.cursor()
            row_count = cursor.execute("""UPDATE A2INVCOSTOSPRECIOS SET FIC_P01PRECIOTOTALEXT = PRECIO
                            FROM A2INVCOSTOSPRECIOS
                            INNER JOIN "%s\\TMPDJANGO%s" ON SKU = FIC_CODEITEM 
                            WHERE FIC_CODEITEM NOT IN (SELECT FO_PRODUCTO FROM SINVOFERTA WHERE ('%s' BETWEEN FO_FECHAINICIO AND FO_FECHAFINAL) AND FO_VISIBLE = 1 ) """ 
                        % (self.tmp_table_tasks, name_table, datetime.now().strftime('%Y-%m-%d')))
            print(f"Rows updated: {row_count.rowcount}")
            conn.commit()