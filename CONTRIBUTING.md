# Contribuir a Doctor-ku

Gracias por interesarte en el proyecto. Toda ayuda es bienvenida: bugs, docs, tests o mejoras de remediación.

## Antes de empezar

1. Revisá [README.md](README.md) y la sección **Limitaciones** (remediación destructiva).
2. **No commitees secretos**: claves SSH, tokens k3s, kubeconfig, `helm/secrets.yaml`, `.env`.
3. **No incluyas `.venv/`** ni dependencias locales — usá `pip install -r requirements.txt` en tu entorno.

## Cómo reportar bugs

1. Buscá si ya existe un [issue](https://github.com/ghcetraro/doctor-ku/issues) similar.
2. Abrí uno nuevo con:
   - Versión / tag de imagen o commit
   - Configuración relevante (sin secretos; IPs/hostnames de ejemplo están bien)
   - Logs del Job o de `python -m app.runner`
   - Comportamiento esperado vs actual

Para vulnerabilidades, seguí [SECURITY.md](SECURITY.md).

## Pull requests

1. Fork del repo y branch desde `main`:
   ```bash
   git checkout -b feature/mi-cambio
   ```
2. Cambios acotados y con mensajes de commit claros en español o inglés.
3. Verificá localmente:
   ```bash
   pip install -r requirements.txt
   python -m py_compile app/*.py
   helm template test ./helm -f helm/values-production.yaml > /dev/null
   ```
4. Actualizá documentación si cambiás comportamiento, Helm o configuración.
5. Abrí el PR describiendo el **por qué** del cambio.

## Estilo de código

- Python 3.12+, tipos donde aporten claridad
- Seguir el estilo del código existente (nombres en minúscula, logs en español)
- Cambios mínimos: evitar refactors no relacionados al PR

## Releases

Las versiones se etiquetan en Git (`v1.0.0`, `v1.1.0`, …) y se documentan en [CHANGELOG.md](CHANGELOG.md).
Ver [docs/releases.md](docs/releases.md) para el flujo de release e imagen Docker.

## Preguntas

Abrí un issue con la etiqueta `question` o comentá en el PR de discusión.
