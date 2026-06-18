# Dashboard-Censo-2024
Dashboard with data from the 2024 Census to analyze housing tenure in Chile, comparing professionals and non-professionals.

## Estructura del Proyecto

*   `app.py`: La aplicación principal del dashboard interactivo.
*   `process_data.py`: Script de procesamiento local que lee las bases del Censo (que pesan más de 3.2 GB) y genera un archivo ligero y consolidado.
*   `aggregated_data.json`: El archivo consolidado y ligero (< 150 KB) generado por `process_data.py` que contiene los datos agregados para los gráficos.
*   `requirements.txt`: Archivo de dependencias necesarias para ejecutar la app en local o en la nube.
*   `Análisis_D2.ipynb`: El notebook original de análisis y visualización.
