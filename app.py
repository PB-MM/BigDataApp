from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from pymongo.mongo_client import MongoClient
from pymongo.server_api import ServerApi
import zipfile
import os
from datetime import datetime
import json
import re
from elasticsearch import Elasticsearch
import tempfile
import shutil

app = Flask(__name__)
app.secret_key = 'tu_clave_secreta_aqui'  # Cambia esto por una clave secreta segura

# Agregar la función now al contexto de la plantilla
@app.context_processor
def inject_now():
    return {'now': datetime.now}

# Versión de la aplicación
VERSION_APP = "Versión 2.2 del Mayo 22 del 2025"
CREATOR_APP = "Paula Bohorquez/PB-MM BigDataApp"
mongo_uri   = os.environ.get("MONGO_URI")

if not mongo_uri:
    #uri = "mongodb+srv://DbCentral:DbCentral2025@cluster0.vhltza7.mongodb.net/?appName=Cluster0"
    uri         = "mongodb+srv://pbohorquezm:Jeyy.910615@cluster0.z3vyy.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0"
    mongo_uri   = uri

# Función para conectar a MongoDB
def connect_mongo():
    try:
        client = MongoClient(mongo_uri, server_api=ServerApi('1'))
        client.admin.command('ping')
        print("Conexión exitosa a MongoDB!")
        return client
    except Exception as e:
        print(f"Error al conectar a MongoDB: {e}")
        return None

# Configuración de Elasticsearch
client = Elasticsearch(
    "https://my-elasticsearch-project-f56628.es.us-east-1.aws.elastic.cloud:443",
    api_key="dkIzMVBKY0J5RXlGWUlEUUxXWDA6Ym5CZlNMZ0xmVHBpMDQ4Z2hpN2JEUQ=="
)
INDEX_NAME = "ucentral_paula"

@app.route('/')
def index():
    return render_template('index.html', version=VERSION_APP,creador=CREATOR_APP)

@app.route('/about')
def about():
    return render_template('about.html', version=VERSION_APP,creador=CREATOR_APP)

@app.route('/contacto', methods=['GET', 'POST'])
def contacto():
    if request.method == 'POST':
        # 1) Leer los campos del formulario
        nombre  = request.form.get('nombre')
        email   = request.form.get('email')
        asunto  = request.form.get('asunto')
        mensaje = request.form.get('mensaje')

        # 2) Conectarse a MongoDB
        client = connect_mongo()
        if not client:
            # Si no se pudo conectar, renderizamos contacto.html con mensaje de error
            error_msg = 'Error de conexión con la base de datos. Intenta nuevamente más tarde.'
            return render_template(
                'contacto.html',
                error_message=error_msg,
                version=VERSION_APP,
                creador=CREATOR_APP
            )

        try:
            # 3) Acceder (o crear) base de datos y colección
            db = client['contactos']            # Base de datos llamada "contactos"
            contactos_coll = db['contactos']    # Colección "contactos"

            # 4) Construir el documento a insertar
            nuevo_contacto = {
                'nombre': nombre,
                'email': email,
                'asunto': asunto,
                'mensaje': mensaje,
                'fecha_envio': datetime.utcnow()
            }

            # 5) Insertar el documento
            contactos_coll.insert_one(nuevo_contacto)

            # 6) Cerrar la conexión antes de renderizar
            client.close()

            # 7) Renderizar la misma plantilla con un mensaje de éxito
            return render_template(
                'contacto.html',
                success_message="¡Gracias! Tu mensaje se envió correctamente.",
                version=VERSION_APP,
                creador=CREATOR_APP
            )

        except Exception as e:
            # Si ocurre algún error al insertar, cerramos conexión y devolvemos mensaje de error
            client.close()
            error_msg = f'No se pudo guardar tu mensaje: {str(e)}'
            return render_template(
                'contacto.html',
                error_message=error_msg,
                version=VERSION_APP,
                creador=CREATOR_APP
            )

    # Si el método es GET, simplemente renderizar contacto.html sin mensajes
    return render_template(
        'contacto.html',
        version=VERSION_APP,
        creador=CREATOR_APP
    )


# ----------------------------------------
# EJECUCIÓN DE LA APP
# ----------------------------------------
if __name__ == '__main__':
    app.run(debug=True)

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        # Primero verificar la conectividad con MongoDB
        client = connect_mongo()
        if not client:
            return render_template('login.html', error_message='Error de conexión con la base de datos. Por favor, intente más tarde.', version=VERSION_APP,creador=CREATOR_APP)
        
        try:
            db = client['administracion']
            security_collection = db['seguridad']
            usuario = request.form['usuario']
            password = request.form['password']
            # Verificar credenciales en MongoDB
            user = security_collection.find_one({
                'usuario': usuario,
                'password': password
            })
            
            if user:
                session['usuario'] = usuario
                return redirect(url_for('gestion_proyecto'))
            else:
                return render_template('login.html', error_message='Usuario o contraseña incorrectos', version=VERSION_APP,creador=CREATOR_APP)
        except Exception as e:
            return render_template('login.html', error_message=f'Error al validar credenciales: {str(e)}', version=VERSION_APP,creador=CREATOR_APP)
            
        finally:
            client.close()
    
    return render_template('login.html', version=VERSION_APP,creador=CREATOR_APP)

@app.route('/listar-usuarios')
def listar_usuarios():
    try:
        client = connect_mongo()
        if not client:
            return jsonify({'error': 'Error de conexión con la base de datos'}), 500
        
        db = client['administracion']
        security_collection = db['seguridad']
        
        # Obtener todos los usuarios, excluyendo la contraseña por seguridad
        #usuarios = list(security_collection.find({}, {'password': 0}))

        usuarios = list(security_collection.find())
        
        # Convertir ObjectId a string para serialización JSON
        for usuario in usuarios:
            usuario['_id'] = str(usuario['_id'])
        
        return jsonify(usuarios)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'client' in locals():
            client.close()

@app.route('/gestion_proyecto', methods=['GET', 'POST'])
def gestion_proyecto():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        client = connect_mongo()
        # Obtener lista de bases de datos
        databases = client.list_database_names()
        # Eliminar bases de datos del sistema
        system_dbs = ['admin', 'local', 'config']
        databases = [db for db in databases if db not in system_dbs]
        
        selected_db = request.form.get('database') if request.method == 'POST' else request.args.get('database')
        collections_data = []
        
        if selected_db:
            db = client[selected_db]
            collections = db.list_collection_names()
            for index, collection_name in enumerate(collections, 1):
                collection = db[collection_name]
                count = collection.count_documents({})
                collections_data.append({
                    'index': index,
                    'name': collection_name,
                    'count': count
                })
        
        return render_template('gestion/index.html',
                            databases=databases,
                            selected_db=selected_db,
                            collections_data=collections_data,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/index.html',
                            error_message=f'Error al conectar con MongoDB: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/crear-coleccion-form/<database>')
def crear_coleccion_form(database):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('gestion/crear_coleccion.html', 
                        database=database,
                        usuario=session['usuario'],
                        version=VERSION_APP,
                        creador=CREATOR_APP)

@app.route('/crear-coleccion', methods=['POST'])
def crear_coleccion():
    if 'usuario' not in session:
        return redirect(url_for('login'))

    # 1) Leer datos del formulario
    database       = request.form.get('database')
    collection_name = request.form.get('collection_name')
    zip_file       = request.files.get('zip_file')

    # 2) Validar campos requeridos
    if not all([database, collection_name, zip_file]):
        return render_template(
            'gestion/crear_coleccion.html',
            error_message='Todos los campos son requeridos',
            database=database,
            usuario=session['usuario'],
            version=VERSION_APP,
            creador=CREATOR_APP
        )

    # 3) Conectarse a MongoDB
    client = connect_mongo()
    if not client:
        return render_template(
            'gestion/crear_coleccion.html',
            error_message='Error de conexión con MongoDB',
            database=database,
            usuario=session['usuario'],
            version=VERSION_APP,
            creador=CREATOR_APP
        )

    try:
        # 4) Preparar la colección (esto no inserta nada hasta procesar JSONs)
        db         = client[database]
        collection = db[collection_name]

        # 5) Crear un directorio temporal (con tempfile) para almacenar el ZIP y extraer
        temp_dir = tempfile.mkdtemp(prefix='mongo_upload_')
        try:
            # 5.1) Guardar el ZIP en disco
            zip_path = os.path.join(temp_dir, zip_file.filename)
            zip_file.save(zip_path)

            # 5.2) Abrir el ZIP y extraerlo en el mismo temp_dir
            with zipfile.ZipFile(zip_path, 'r') as zf:
                zf.extractall(temp_dir)

            # 6) Recorrer todos los archivos extraídos y procesar solo los .json
            for root, _, files in os.walk(temp_dir):
                for filename in files:
                    if filename.lower().endswith('.json'):
                        file_path = os.path.join(root, filename)
                        with open(file_path, 'r', encoding='utf-8') as f:
                            try:
                                json_data = json.load(f)
                            except json.JSONDecodeError:
                                # Si no es un JSON válido, lo saltamos
                                print(f"[WARN] JSON inválido: {filename}")
                                continue

                            # 6.1) Si viene una lista de objetos, insertar todos; si no, uno solo
                            if isinstance(json_data, list):
                                collection.insert_many(json_data)
                            else:
                                collection.insert_one(json_data)

        finally:
            # 7) Eliminar recursivamente el directorio temporal
            shutil.rmtree(temp_dir)

        # 8) Redirigir de vuelta a la lista de colecciones
        return redirect(url_for('gestion_proyecto', database=database))

    except Exception as e:
        # 9) En caso de error, mostrar mensaje en la misma página de carga
        return render_template(
            'gestion/crear_coleccion.html',
            error_message=f'Error al crear la colección: {str(e)}',
            database=database,
            usuario=session['usuario'],
            version=VERSION_APP,
            creador=CREATOR_APP
        )

    finally:
        # 10) Cerrar conexión con MongoDB si existe
        if 'client' in locals():
            client.close()

@app.route('/ver-registros/<database>/<collection>')
def ver_registros(database, collection):
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        client = connect_mongo()
        if not client:
            return render_template('gestion/index.html',
                                error_message='Error de conexión con MongoDB',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        db = client[database]
        collection_obj = db[collection]
        
        # Obtener los primeros 100 registros por defecto
        records = list(collection_obj.find().limit(100))
        
        # Convertir ObjectId a string para serialización JSON
        for record in records:
            record['_id'] = str(record['_id'])
        
        return render_template('gestion/ver_registros.html',
                            database=database,
                            collection_name=collection,
                            records=records,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/index.html',
                            error_message=f'Error al obtener registros: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    finally:
        if 'client' in locals():
            client.close()

@app.route('/obtener-registros', methods=['POST'])
def obtener_registros():
    if 'usuario' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        database = request.form.get('database')
        collection = request.form.get('collection')
        limit = int(request.form.get('limit', 100))
        
        client = connect_mongo()
        if not client:
            return jsonify({'error': 'Error de conexión con MongoDB'}), 500
        
        db = client[database]
        collection_obj = db[collection]
        
        # Obtener los registros con el límite especificado
        records = list(collection_obj.find().limit(limit))
        
        # Convertir ObjectId a string para serialización JSON
        for record in records:
            record['_id'] = str(record['_id'])
        
        return jsonify({'records': records})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        if 'client' in locals():
            client.close()

@app.route('/crear-base-datos-form')
def crear_base_datos_form():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    return render_template('gestion/crear_base_datos.html',
                        version=VERSION_APP,
                        creador=CREATOR_APP,
                        usuario=session['usuario'])

@app.route('/crear-base-datos', methods=['POST'])
def crear_base_datos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        database_name = request.form.get('database_name')
        collection_name = request.form.get('collection_name')
        
        # Validar que los nombres no contengan caracteres especiales
        valid_pattern = re.compile(r'^[a-zA-Z0-9_]+$')
        if not valid_pattern.match(database_name) or not valid_pattern.match(collection_name):
            return render_template('gestion/crear_base_datos.html',
                                error_message='Los nombres no pueden contener tildes, espacios ni caracteres especiales',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        # Conectar a MongoDB
        client = connect_mongo()
        if not client:
            return render_template('gestion/crear_base_datos.html',
                                error_message='Error de conexión con MongoDB',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
        
        # Crear la base de datos y la colección
        db = client[database_name]
        collection = db[collection_name]
        
        # Insertar un documento vacío para crear la colección
        collection.insert_one({})
        
        # Eliminar el documento vacío
        collection.delete_one({})
        
        return redirect(url_for('gestion_proyecto', database=database_name))
        
    except Exception as e:
        return render_template('gestion/crear_base_datos.html',
                            error_message=f'Error al crear la base de datos: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    finally:
        if 'client' in locals():
            client.close()

@app.route('/logout')
def logout():
    # Limpiar todas las variables de sesión
    session.clear()
    # Redirigir al index principal
    return redirect(url_for('index'))

@app.route('/elasticAdmin')
def elasticAdmin():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        # Obtener información del índice
        index_info = client.indices.get(index=INDEX_NAME)
        doc_count = client.count(index=INDEX_NAME)['count']
        
        return render_template('gestion/ver_elasticAdmin.html',
                            index_name=INDEX_NAME,
                            doc_count=doc_count,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/ver_elasticAdmin.html',
                            error_message=f'Error al conectar con Elasticsearch: {str(e)}',
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/elastic-agregar-documentos', methods=['GET', 'POST'])
def elastic_agregar_documentos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        try:
            if 'zipFile' not in request.files:
                return render_template('gestion/elastic_agregar_documentos.html',
                                    error_message='No se ha seleccionado ningún archivo',
                                    index_name=INDEX_NAME,
                                    version=VERSION_APP,
                                    creador=CREATOR_APP,
                                    usuario=session['usuario'])
            
            zip_file = request.files['zipFile']
            if zip_file.filename == '':
                return render_template('gestion/elastic_agregar_documentos.html',
                                    error_message='No se ha seleccionado ningún archivo',
                                    index_name=INDEX_NAME,
                                    version=VERSION_APP,
                                    creador=CREATOR_APP,
                                    usuario=session['usuario'])
            
            # Crear directorio temporal
            temp_dir = os.path.join(os.path.dirname(__file__), 'temp')
            os.makedirs(temp_dir, exist_ok=True)
            
            # Guardar y extraer el archivo ZIP
            zip_path = os.path.join(temp_dir, zip_file.filename)
            zip_file.save(zip_path)
            
            with zipfile.ZipFile(zip_path) as zip_ref:
                zip_ref.extractall(temp_dir)
            
            # Procesar archivos JSON
            success_count = 0
            error_count = 0
            
            for root, _, files in os.walk(temp_dir):
                for file in files:
                    if file.endswith('.json'):
                        file_path = os.path.join(root, file)
                        try:
                            with open(file_path, 'r', encoding='utf-8') as f:
                                json_data = json.load(f)
                                if isinstance(json_data, list):
                                    for doc in json_data:
                                        client.index(index=INDEX_NAME, document=doc)
                                        success_count += 1
                                else:
                                    client.index(index=INDEX_NAME, document=json_data)
                                    success_count += 1
                        except Exception as e:
                            error_count += 1
                            print(f"Error procesando {file}: {str(e)}")
            
            # Limpiar archivos temporales
            for root, dirs, files in os.walk(temp_dir, topdown=False):
                for file in files:
                    os.remove(os.path.join(root, file))
                for dir in dirs:
                    os.rmdir(os.path.join(root, dir))
            os.rmdir(temp_dir)
            
            return render_template('gestion/elastic_agregar_documentos.html',
                                success_message=f'Se indexaron {success_count} documentos exitosamente. Errores: {error_count}',
                                index_name=INDEX_NAME,
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
            
        except Exception as e:
            return render_template('gestion/elastic_agregar_documentos.html',
                                error_message=f'Error al procesar el archivo: {str(e)}',
                                index_name=INDEX_NAME,
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                usuario=session['usuario'])
    
    return render_template('gestion/elastic_agregar_documentos.html',
                         index_name=INDEX_NAME,
                         version=VERSION_APP,
                         creador=CREATOR_APP,
                         usuario=session['usuario'])

@app.route('/elastic-listar-documentos')
def elastic_listar_documentos():
    if 'usuario' not in session:
        return redirect(url_for('login'))
    
    try:
        # Obtener los primeros 100 documentos
        response = client.search(
            index=INDEX_NAME,
            body={
                "query": {"match_all": {}},
                "size": 100
            }
        )
        
        documents = response['hits']['hits']
        
        return render_template('gestion/elastic_listar_documentos.html',
                            index_name=INDEX_NAME,
                            documents=documents,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])
    except Exception as e:
        return render_template('gestion/elastic_listar_documentos.html',
                            error_message=f'Error al obtener documentos: {str(e)}',
                            index_name=INDEX_NAME,
                            version=VERSION_APP,
                            creador=CREATOR_APP,
                            usuario=session['usuario'])

@app.route('/elastic-eliminar-documento', methods=['POST'])
def elastic_eliminar_documento():
    if 'usuario' not in session:
        return jsonify({'error': 'No autorizado'}), 401
    
    try:
        doc_id = request.form.get('doc_id')
        if not doc_id:
            return jsonify({'error': 'ID de documento no proporcionado'}), 400
        
        response = client.delete(index=INDEX_NAME, id=doc_id)
        
        if response['result'] == 'deleted':
            return jsonify({'success': True})
        else:
            return jsonify({'error': 'Error al eliminar el documento'}), 500
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/buscador', methods=['GET', 'POST'])
def buscador():
    if request.method == 'POST':
        try:
            # Obtener los parámetros del formulario
            search_type = request.form.get('search_type')
            search_text = request.form.get('search_text')
            fecha_desde = request.form.get('fecha_desde')
            fecha_hasta = request.form.get('fecha_hasta')

            # Establecer fechas por defecto si están vacías
            if not fecha_desde:
                fecha_desde = "1500-01-01"
            if not fecha_hasta:
                fecha_hasta = datetime.now().strftime("%Y-%m-%d")

            # Construir la consulta base
            query = {
                "query": {
                    "bool": {
                        "must": []
                    }
                },
                "aggs": {
                    "categoria": {
                        "terms": {
                            "field": "categoria",
                            "size": 10,
                            "order": {"_key": "asc"}
                        }
                    },
                    "clasificacion": {
                        "terms": {
                            "field": "clasificacion",
                            "size": 10,
                            "order": {"_key": "asc"}
                        }
                    },
                    "Fecha": {
                        "date_histogram": {
                            "field": "fecha",
                            "calendar_interval": "year",
                            "format": "yyyy"
                        }
                    }
                }
            }

            # Agregar condición de búsqueda según el tipo
            if search_type == 'texto':
                query["query"]["bool"]["must"].extend([
                    {
                        "match_phrase": {
                            "texto": {
                                "query": search_text,
                                "slop": 1
                            }
                        }
                    }
                ])
            else:           #si no es una búsqueda por texto
                pattern = f"*{search_text}*"
                query["query"]["bool"]["must"].append({
                    "wildcard": {
                        search_type: {
                            "value": pattern,
                            "case_insensitive": True
                        }
                    }
                })

            # Agregar rango de fechas
            range_query = {
                "range": {
                    "fecha": {
                        "format": "yyyy-MM-dd",
                        "gte": fecha_desde,
                        "lte": fecha_hasta
                    }
                }
            }
            query["query"]["bool"]["must"].append(range_query)

            # Ejecutar la búsqueda en Elasticsearch
            response = client.search(
                index=INDEX_NAME,
                body=query
            )

            # Preparar los resultados para la plantilla
            hits         = response['hits']['hits']
            aggregations = response['aggregations']

            return render_template('buscador.html',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                hits=hits,
                                aggregations=aggregations,
                                search_type=search_type,
                                search_text=search_text,
                                fecha_desde=fecha_desde,
                                fecha_hasta=fecha_hasta,
                                query=query)
        
        except Exception as e:
            return render_template('buscador.html',
                                version=VERSION_APP,
                                creador=CREATOR_APP,
                                error_message=f'Error en la búsqueda: {str(e)}')
    
    return render_template('buscador.html',
                        version=VERSION_APP,
                        creador=CREATOR_APP)

@app.route('/api/search', methods=['POST'])
def search():
    try:
        data = request.get_json()
        index_name = data.get('index', 'ucentral_test')
        query = data.get('query')

        # Ejecutar la búsqueda en Elasticsearch
        response = client.search(
            index=index_name,
            body=query
        )

        return jsonify(response)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)