import pyodbc
from decouple import config
from datetime import datetime
from pydbisam import PyDBISAM
import uuid
from datetime import datetime

class DBISAMDatabase:
    def __init__(self):
        self.dsn = config('DSN')
        self.catalog = config('CatalogName')
        print('INIT', self.catalog, self.dsn)
        #self.tmp_table_tasks = settings.DBISAM_DATABASE['TMP_TABLE_TASKS']

    def connect_dbisam(self):
        conn = pyodbc.connect(f'DSN={self.dsn};CatalogName={self.catalog}')
        return conn
    
    def consultar_vendedores_con_acceso(self):
        try:
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    vendedores=cursor.execute("SELECT FV_TELEFONOS FROM SVENDEDORES WHERE FV_STATUS = 1 --AND FV_ACCESOWHATSAPP = 1").fetchall()
                    if vendedores is None:
                        return None
                    return [vendedor.FV_TELEFONOS for vendedor in vendedores]    
        except Exception as e:
            return(str(e))

    def consultar_vendedor(self, telefono: str):
        try:
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    vendedor=cursor.execute(f"SELECT FV_CODIGO, FV_DESCRIPCION FROM SVENDEDORES WHERE FV_TELEFONOS = '{telefono}' AND FV_STATUS = 1").fetchone()
                    if vendedor is None:
                        return None
                    return [vendedor.FV_CODIGO, vendedor.FV_DESCRIPCION]   
        except Exception as e:
            return(str(e))

    def consultar_cliente(self, cliente: str, vendedor:str):
        try:
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    cliente_encontrado=cursor.execute(f"SELECT FC_CODIGO, FC_DESCRIPCION, FC_DIRECCION1 FROM SCLIENTES WHERE FC_CODIGO = '{cliente}' AND FC_VENDEDOR = '{vendedor}' AND FC_STATUS = 1").fetchone()
                    if cliente_encontrado is None:
                        return None
                    return [cliente_encontrado.FC_DESCRIPCION, cliente_encontrado.FC_DIRECCION1]
        except Exception as e:
            return(str(e))
            

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
            
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    productos=cursor.execute(f"""SELECT FI_CODIGO, 
                                        CASE WHEN FIC_IMP01ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN 16
                                             WHEN FIC_IMP02ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN 8
                                             WHEN FIC_IMP01ACTIVO = 0 AND FIC_IMP01EXENTO = 1 THEN 0
                                        ELSE 0
                                        END AS IMPUESTO,
                                        FIC_{precios.get(tipo_precio)}PRECIOTOTALEXT,
                                        FI_DESCRIPCION             
                                     FROM SINVENTARIO
                                     INNER JOIN A2INVCOSTOSPRECIOS ON FIC_CODEITEM = FI_CODIGO
                                     WHERE FI_STATUS = 1 AND FI_CODIGO IN {parse_products}""").fetchall()
                    print(productos)
                    return productos    
        except Exception as e:
            print(str(e))
            return str(e)   
        
    def insert_cliente(self, cliente: dict, tlf_vendedor: str):
        try:
            direccion =  cliente['registrar']['direccion'] + "'+#10+'" + "'+#13+'" 
            nombre = cliente['registrar']['name']
            correo = cliente['registrar']['email']
            telefono = cliente['registrar']['phone']
            rif = cliente['registrar']['rif']
            tipo = cliente['registrar']['tipo']
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    vendedor = cursor.execute(f"SELECT FV_CODIGO, FV_ZONAVENTA FROM SVENDEDORES WHERE FV_TELEFONOS = '{tlf_vendedor}' AND FV_STATUS = 1 ").fetchone()
                    query = """INSERT INTO SCLIENTES 
                                                (FC_CODIGO, FC_DESCRIPCION, FC_STATUS, FC_CLASIFICACION, 
                                                FC_RIF, FC_DIRECCION1, FC_TELEFONO, FC_EMAIL,
                                                FC_ZONA, FC_VENDEDOR, FC_LIMITECREDITO, FC_FECHANACIMIENTO,
                                                FC_MONEDA)
                                            VALUES('{rif}', '{nombre}', 1, '{clasificacion}', 
                                                   '{rif}', '{direccion}', '{telefono}', '{email}',
                                                   '{zona}', '{vendedor}', 0.01, '{fecha}', '2')""".format(rif=rif, nombre=nombre.upper(), clasificacion=tipo, 
                                                                                                      direccion=direccion, telefono=telefono, email=correo, 
                                                                                                      zona=vendedor.FV_ZONAVENTA, vendedor=vendedor.FV_CODIGO, fecha=datetime.now().strftime('%Y-%m-%d'))
                    print(query)
                    row = cursor.execute(query).rowcount
                    cursor.commit()
                    return row
        except pyodbc.Error as e:
            print(e)
            return str(e)   

    def insert_pedidos(self, pedido):
        try:
            detalle_query = []
            linea = 0
            ID_PEDIDO = f"WS{uuid.uuid4().hex[:10].upper()}"  
            for codigo, detalles in pedido['productos'].items():
                    detalle_query.append(f"""INSERT INTO SDETALLEVENTA 
                                                        (FDI_DOCUMENTO,
                                                        FDI_CLIENTEPROVEEDOR,
                                                        FDI_STATUS,
                                                        FDI_MONEDA,
                                                        FDI_VISIBLE,
                                                        FDI_DEPOSITOSOURCE,
                                                        FDI_USADEPOSITOS, 
                                                        FDI_TIPOOPERACION, 
                                                        FDI_CODIGO, 
                                                        FDI_CANTIDAD,
                                                        FDI_CANTIDADPENDIENTE, 
                                                        FDI_PRECIODEVENTA, 
                                                        FDI_PRECIOBASECOMISION, 
                                                        FDI_OPERACION_AUTOINCREMENT, 
                                                        FDI_LINEA,
                                                        FDI_IMPUESTO1,
                                                        FDI_PORCENTIMPUESTO1,
                                                        FDI_MONTOIMPUESTO1,
                                                        FDI_PORCENTDESCPARCIAL,
                                                        FDI_DESCUENTOPARCIAL,
                                                        FDI_PRECIOSINDESCUENTO,
                                                        FDI_PRECIOCONDESCUENTO,
                                                        FDI_PRECIODEVENTA,
                                                        FDI_UNDDESCARGA,
                                                        FDI_UNDCAPACIDAD,
                                                        FDI_VENDEDORASIGNADO,
                                                        FDI_PRECIOBASECOMISION,
                                                        FDI_COMISIONBLOQUEADA,
                                                        FDI_FECHAOPERACION
                                                        )
                                              VALUES ('{pedido['id']}',
                                                        '{pedido['cliente']}', 
                                                        4,
                                                        2,
                                                        1,
                                                        1,
                                                        1,
                                                        10, 
                                                        '{codigo}', 
                                                        {detalles['cantidad']},
                                                        {detalles['cantidad']}, 
                                                        {detalles['precio']}, 
                                                        {detalles['subtotal']},
                                                        LASTAUTOINC('SOPERACIONINV'), 
                                                        {linea},
                                                        {detalles['impuesto']},
                                                        {1 if detalles['impuesto'] == 16 else 0},
                                                        {detalles['monto_iva']},
                                                        {detalles['descuento']},
                                                        {round(detalles['precio_sin_iva'] * (detalles['descuento']/ 100), 2)},
                                                        {detalles['precio_sin_iva']},
                                                        {detalles['precio_con_descuento']},
                                                        {detalles['precio_venta']},
                                                        1,
                                                        1,
                                                        '{pedido['vendedor']}',
                                                        {detalles['precio_con_descuento']},
                                                        0,
                                                        '{datetime.now().strftime('%Y-%m-%d')}'
                                                        )
                                                        ;""")
                    linea += 1
            print(detalle_query[0])
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    comentario = pedido['comentario'].replace("\r", "'+#13+'").replace("\n", "'+#10+'")
                    cursor.execute(f"""START TRANSACTION;
                                      INSERT INTO SOPERACIONINV (FTI_DOCUMENTO, 
                                                                 FTI_TIPO, 
                                                                 FTI_STATUS,
                                                                 FTI_VISIBLE,
                                                                 FTI_FECHAEMISION,
                                                                 FTI_DEPOSITOSOURCE,
                                                                 FTI_TOTALITEMS,
                                                                 FTI_TOTALITEMSINICIAL,
                                                                 FTI_MONEDA,
                                                                 FTI_RESPONSABLE,
                                                                 FTI_DETALLE, 
                                                                 FTI_TIENELOTES,
                                                                 FTI_UPDATEITEMS,
                                                                 FTI_TOTALBRUTO,
                                                                 FTI_DESCUENTO1PORCENT,
                                                                 FTI_DESCUENTO1MONTO,
                                                                 FTI_DESCUENTO1ORIGEN,
                                                                 FTI_BASEIMPONIBLE,
                                                                 FTI_IMPUESTO1PORCENT,
                                                                 FTI_IMPUESTO1MONTO,     
                                                                 FTI_TOTALNETO,
                                                                 FTI_RIFCLIENTE,
                                                                 FTI_PERSONACONTACTO,
                                                                 FTI_VENDEDORASIGNADO,
                                                                 FTI_HORA)
                                        VALUES ('{pedido['id']}', 
                                                10, 
                                                4,
                                                1,
                                                '{datetime.now().strftime('%Y-%m-%d')}',
                                                1, 
                                                {len(pedido['productos'])},
                                                {len(pedido['productos'])},
                                                2,
                                                '{pedido['cliente']}',
                                                '{comentario}',
                                                0,
                                                1,
                                                {pedido['total_bruto']}, 
                                                0,
                                                0,
                                                1,
                                                {pedido['baseimponible']},
                                                16,
                                                {pedido['iva_16']},
                                                {pedido['total_neto']},
                                                '{pedido['cliente']}',
                                                '{pedido['descripcion_cliente']}',
                                                '04',
                                                '{datetime.now().strftime("%I:%M:%S %p")}');
                                      {''.join(detalle_query)}  
                                """)
                    cursor.execute("COMMIT;")
                    #print(count, 'filas insertadas')
                    #cursor.execute("""""")
                    # for codigo, detalles in pedido['productos'].items():
                    #      cursor.execute(f"""INSERT INTO SDETALLEVENTA (FDI_DOCUMENTO, FDI_TIPOOPERACION, FDI_CODIGO, FDI_CANTIDAD, FDI_PRECIODEVENTA, FDI_PRECIOBASECOMISION, FDI_OPERACION_AUTOINCREMENT, FDI_LINEA)
                    #                          VALUES ('00000123', 10, '{codigo}', {detalles['cantidad']}, {detalles['precio']}, {detalles['subtotal']}, LASTAUTOINC('SOPERACIONINV'), 0);""")
                    # cursor.execute("COMMIT;")
                    # conn.commit()   
                #conn.commit()      
        except Exception as e:
            print(e)
            
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