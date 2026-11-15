# Cliente 4.4.0: correcciones de conteo y deteccion de cabezas

## Que cambia al actualizar

- El origen del cruce se comprueba antes de actualizar el lado actual. Un paso que salta el corredor entre frames puede contar IN u OUT.
- No se une el punto actual con un origen remoto para inferir una interseccion que no aparecio en los segmentos consecutivos observados.
- Una ausencia mayor a 2 segundos o un salto mayor a 260 px inicia una trayectoria nueva. Los cortes RTSP reinician el tracker y las trayectorias, conservando los totales.
- No se procesa dos veces el mismo ndarray publicado por la camara. Un stream lento no puede confirmar varias observaciones con una sola imagen.
- Asignacion global de IDs con SciPy en lugar del DP exponencial. Se conservan los costos de asociacion y la supresion de detecciones fusionadas.
- Modelo y clase configurables, con validacion de etiquetas; ROI rectangular opcional, con coordenadas restauradas al frame original.

## Actualizar desde codigo

Cerrar el cliente antes de actualizar. Conservar `.env`, `data` y los logs locales.

```powershell
cd C:\CONTEOPERSONAS
git pull --ff-only origin master
cd client
.\setup_client.bat
.\run_client.bat
```

Si se utiliza el ejecutable instalado, hacer pull NO actualiza ese ejecutable:

```powershell
cd C:\CONTEOPERSONAS\client
.\build_installer.bat
```

Instalar `client\dist\installer\SetupContePersonas.exe` en cada PC. El instalador requiere Inno Setup. Si solo se necesita la carpeta portable, ejecutar `build_client.bat` y distribuir la carpeta completa `dist\ContePersonas`, no solamente el `.exe`. Confirmar version 4.4.0 en el servidor.

## Diferencia con el tutorial

Referencia: https://pysource.com/2021/12/07/how-to-count-people-from-cctv-cameras-with-opencv-and-deep-learning/

El tutorial entrena un detector de cabezas con imagenes del escenario, sigue IDs y cuenta dentro de una ROI. Esta version conserva el conteo direccional IN/OUT por cruce de linea del sistema e incorpora soporte para un detector real de cabezas. No reemplaza IN/OUT por un conteo de ocupacion de area.

El repositorio incluye `yolov8n.pt`, entrenado para personas/cuerpos, NO para cabezas. El modo predeterminado `person` sigue estimando la cabeza desde el cuerpo y conserva el filtro corporal existente. El recuadro de cabeza no convierte ese modelo en un detector de cabezas.

Para deteccion real hacen falta pesos YOLO de deteccion compatibles con Ultralytics, entrenados/validados para cabezas de estas camaras. No se incluyen pesos nuevos ni se ha entrenado un modelo con grabaciones de los locales.

Copiar los pesos a la carpeta del cliente (junto al exe si esta instalado) y configurar, por ejemplo:

```env
DETECTION_TARGET=head
YOLO_MODEL_PATH=heads.pt
YOLO_CLASS_ID=0
```

El ID debe corresponder a la clase de cabeza del modelo. Se aceptan etiquetas `head`, `human head`, `human_head`, `person_head` y `cabeza`. No renombrar las etiquetas de un modelo de personas para saltar esta validacion. El modo head utiliza el centro de la caja detectada; recalibrar la linea mirando ese punto. No aplica el filtro de adultos: una cabeza sola no permite determinar con fiabilidad la edad ni la altura de la persona.

## ROI y rendimiento

Por defecto se procesa todo el frame. Para limitar la deteccion a una puerta, indicar un rectangulo en pixeles de la resolucion original:

```env
DETECTION_ROI=100,50,900,700
```

Es un ejemplo, NO copiar sin medir la imagen propia. La ROI debe incluir la linea y espacio suficiente para detectar origen, cruce y destino en ambos sentidos. En modo person incluir tambien el cuerpo para no empeorar las detecciones. Un recorte puede reducir distractores y trabajo de preprocesamiento, pero no garantiza menor costo de inferencia: YOLO sigue ajustando a `imgsz`. Dejar vacio para desactivar. No cambia coordenadas de linea ni aplica escalado automatico si se cambia de stream/resolucion.

El perfil de segundo plano sigue usando motion gate y FPS adaptativos. El `.env` existente se conserva; no se reducen globalmente los FPS porque eso puede perder pasos rapidos. El peso del paquete PyTorch no se ha reducido; los cambios apuntan al trabajo durante la ejecucion.

## Verificacion y limites

Las pruebas de logica incluyen cruces rapidos, rebotes, IN/OUT simultaneos, perdida de seguimiento, salto durante confirmacion, frames repetidos, reconexion, ROI, modo head y comparacion de la asignacion con un optimo exhaustivo. Las pruebas del detector usan dobles de prueba, no ejecutan inferencia YOLO.

Medicion local aislada (10 tracks x 10 detecciones, mediana de 10 ejecuciones): asignacion anterior 15,337 ms, nueva 0,388 ms. No equivale a una medicion del consumo total ni a un porcentaje de mejora en la PC del local.

No se ejecutaron camaras reales, inferencia con pesos de cabeza ni compilacion Windows en este entorno. Antes de distribuir a todos los locales, validar uno: entrada, salida, vuelta con el mismo ID, dos personas juntas y corte/reconexion. Comparar con conteo manual sobre la misma grabacion. No hay garantia de error cero; las oclusiones, reflejos, posicion de camara y calidad del modelo siguen influyendo.
