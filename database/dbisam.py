import pyodbc
from decouple import config
from datetime import datetime
from pydbisam import PyDBISAM
import uuid
from datetime import datetime
from database.impuestos import slots_impuesto_linea, campos_impuesto_cabecera
from database.consulta_precios import codigos_para_fi_codigo, lista_sql, mapear_resultados
from database.campo_precio import get_campo_precio

# Tasa efectiva de IVA de un ítem: la tasa real vive en FIC_IMP0xMONTO
# (no es un literal 16/8). Cada impuesto se valida con SU propio flag exento.
# Un ítem tiene una sola tasa aplicable, así que la suma da la tasa efectiva.
IMPUESTO_EFECTIVO_SQL = (
    "(CASE WHEN FIC_IMP01ACTIVO = 1 AND FIC_IMP01EXENTO = 0 THEN FIC_IMP01MONTO ELSE 0 END)"
    " + (CASE WHEN FIC_IMP02ACTIVO = 1 AND FIC_IMP02EXENTO = 0 THEN FIC_IMP02MONTO ELSE 0 END)"
)


class DBISAMDatabase:
    def __init__(self, catalog: str | None = None):
        self.dsn = config('DSN')
        self.catalog = catalog if catalog else config('CatalogName')
        print('INIT', self.catalog, self.dsn)
        #self.tmp_table_tasks = settings.DBISAM_DATABASE['TMP_TABLE_TASKS']

    def connect_dbisam(self):
        conn = pyodbc.connect(f'DSN={self.dsn};CatalogName={self.catalog}')
        return conn

    def columnas_precio(self) -> set:
        """Nombres de columna de A2INVCOSTOSPRECIOS, para validar CAMPO_PRECIO.

        Sin logica: solo trae nombres. Quien decide es validar_campo_precio, que
        es pura y se prueba sin DBISAM.
        """
        with self.connect_dbisam() as conn:
            with conn.cursor() as cursor:
                return {
                    c.column_name.upper()
                    for c in cursor.columns(table="A2INVCOSTOSPRECIOS")
                }
    
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
            

    def listar_clientes_de_vendedor(self, vendedor: str) -> list[dict]:
        """Retorna los clientes activos asignados al vendedor, para poblar el Dropdown del Flow."""
        try:
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    filas = cursor.execute(
                        f"SELECT FC_CODIGO, FC_DESCRIPCION FROM SCLIENTES "
                        f"WHERE FC_VENDEDOR = '{vendedor}' AND FC_STATUS = 1 "
                        f"ORDER BY FC_DESCRIPCION"
                    ).fetchall()
                    return [{"id": f.FC_CODIGO, "title": f.FC_DESCRIPCION} for f in filas]
        except Exception as e:
            print("Error en listar_clientes_de_vendedor:", str(e))
            return []

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
        """Consulta precios de los códigos tipeados por el vendedor.

        Un código puede ser un código de barra (SCODEBAR), un FI_CODIGO interno
        o una FI_REFERENCIA. Devuelve (result_map, not_found).
        """
        precios = {'P1': 'P01', 'P2': 'P02', 'P3': 'P03'}
        sufijo = precios.get(tipo_precio)
        if sufijo is None:
            # Antes esto producía FIC_NonePRECIOTOTALEXT y un error de sintaxis
            # de DBISAM imposible de rastrear hasta acá.
            raise ValueError(
                f"tipo_precio invalido: {tipo_precio!r}. Esperado uno de {sorted(precios)}"
            )
        if not productos:
            return {}, []

        try:
            lista_tipeados = lista_sql(productos)
            with self.connect_dbisam() as conn:
                with conn.cursor() as cursor:
                    codebar = cursor.execute(
                        f"""SELECT FBARRA_CODE, FBARRA_PRODUCTO
                            FROM SCODEBAR
                            WHERE FBARRA_CODE IN {lista_tipeados}"""
                    ).fetchall()
                    por_barra = {x[1]: x[0] for x in codebar}

                    codigos_internos = codigos_para_fi_codigo(productos, por_barra)

                    query = f"""SELECT FI_CODIGO,
                                       {IMPUESTO_EFECTIVO_SQL} AS IMPUESTO,
                                       FIC_{sufijo}{get_campo_precio()},
                                       FI_DESCRIPCION,
                                       FI_PESOPRODUCTO,
                                       FI_REFERENCIA
                                FROM SINVENTARIO
                                INNER JOIN A2INVCOSTOSPRECIOS ON FIC_CODEITEM = FI_CODIGO
                                WHERE FI_STATUS = 1
                                  AND (FI_CODIGO IN {lista_sql(codigos_internos)}
                                       OR FI_REFERENCIA IN {lista_tipeados})"""
                    filas = cursor.execute(query).fetchall()
                    return mapear_resultados(filas, productos, por_barra)
        except pyodbc.Error as e:
            print("Error en lectura de precios", str(e))
            raise pyodbc.DatabaseError(e)
        
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
            cab = campos_impuesto_cabecera(pedido)
            for codigo, detalles in pedido['productos'].items():
                slots = slots_impuesto_linea(detalles['impuesto'], detalles['monto_iva'])
                # Nota: se eliminaron las declaraciones duplicadas de FDI_PRECIODEVENTA y
                # FDI_PRECIOBASECOMISION que existían antes (una en cada par columna/valor).
                # FDI_PORCENTIMPUESTO1 ahora refleja si el ítem tiene algún impuesto (>0).
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
                                                        FDI_OPERACION_AUTOINCREMENT,
                                                        FDI_LINEA,
                                                        FDI_IMPUESTO1,
                                                        FDI_PORCENTIMPUESTO1,
                                                        FDI_MONTOIMPUESTO1,
                                                        FDI_IMPUESTO2,
                                                        FDI_PORCENTIMPUESTO2,
                                                        FDI_MONTOIMPUESTO2,
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
                                                        LASTAUTOINC('SOPERACIONINV'),
                                                        {linea},
                                                        {slots['imp1']},
                                                        {slots['porc1']},
                                                        {slots['monto1']},
                                                        {slots['imp2']},
                                                        {slots['porc2']},
                                                        {slots['monto2']},
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
                                                                 FTI_DETALLECOMENTARIO, 
                                                                 FTI_TIENELOTES,
                                                                 FTI_UPDATEITEMS,
                                                                 FTI_TOTALBRUTO,
                                                                 FTI_DESCUENTO1PORCENT,
                                                                 FTI_DESCUENTO1MONTO,
                                                                 FTI_DESCUENTO1ORIGEN,
                                                                 FTI_BASEIMPONIBLE,
                                                                 FTI_IMPUESTO1PORCENT,
                                                                 FTI_IMPUESTO1MONTO,
                                                                 FTI_BASEIMPONIBLE2,
                                                                 FTI_IMPUESTO2PORCENT,
                                                                 FTI_IMPUESTO2MONTO,
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
                                                {cab['base_imponible']},
                                                {cab['imp1_porcent']},
                                                {cab['imp1_monto']},
                                                {cab['base_imponible2']},
                                                {cab['imp2_porcent']},
                                                {cab['imp2_monto']},
                                                {pedido['total_neto']},
                                                '{pedido['cliente']}',
                                                '{pedido['descripcion_cliente']}',
                                                '{pedido['vendedor']}',
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

#test = DBISAMDatabase()
#test.consultar_precios(['01010024', '01010026', '535', '7591002000011'], 'P1')