# PROTOTIPOS

Autora: Lydia Blanco Ruiz.

En esta carpeta se encuentran los archivos de prueba que se han ido generando durante el desarrollo del proyecto. La función de cada archivo es:

- BaseDatos.py
- Prompt.py
- PruebaBaseDatos.py
- PrototipoRAG.py
- Flask/
- Flask_docker/
- Markdown/
  - Intento1_Markdown.py
  - Markdown_Ocr.py
  - Markdown_Ollama.py 
  - Markdown_Ollama2.py
  - markdown/
  - markdown_Ocr/
  - markdown_Ollama/
  - pdfs/
- tokenizers/
  - script_tokenize.py
  - script_tokenizer1.py
  - script_tokenizer3.py
  - script_tokenize_segundoModelo.py
  - resumen2.json
  - resumen3.json 
- Web Scraping/
  - DescargarPdf.py
  - DescargarPliegos.py
  - PliegosPlaywrightAsincrono.py
  - PliegosPlaywright.py
  - PliegosSelenium.py
  - pliegos_pdfs.json
  - resultados_playwright_asincrono.json
  - resultados_playwright_asincrono_servidor.json
  - resultados_playwright.json
  - resultados_Selenium.json 



Para ejecutar los archivos de web scraping de la carpeta hay que usar el comando:
pip install -r requirements.txt

Posteriormente hay que instalar los navegadores de playwright con el siguiente comando:
playwright install chromium

Para ejecutar el archivo hay que usar:
 python NombreDelArchivo.py
