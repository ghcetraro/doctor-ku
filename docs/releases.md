# Releases y versionado

Doctor-ku usa [Semantic Versioning](https://semver.org/):

- **MAJOR** — cambios incompatibles en config o comportamiento de remediación
- **MINOR** — funcionalidad nueva compatible
- **PATCH** — correcciones de bugs

## Componentes versionados

| Componente | Ubicación | Ejemplo |
|------------|-----------|---------|
| Git tag | GitHub Releases | `v1.0.0` |
| Helm chart | `helm/Chart.yaml` → `version` | `1.0.0` |
| App / imagen | `helm/Chart.yaml` → `appVersion` y `values-*.yaml` → `base.deployment.tag` | `1.0.0` |
| Changelog | [CHANGELOG.md](../CHANGELOG.md) | Entrada por release |

Mantener alineados `appVersion`, tag de imagen en values y el tag Git `v*`.

## Crear una release

```bash
# 1. Actualizar CHANGELOG.md y helm/Chart.yaml (version + appVersion)
# 2. Actualizar tag en helm/values-production.yaml y values-development.yaml

git add CHANGELOG.md helm/
git commit -m "Release v1.0.0"
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin main --tags
```

En GitHub: **Releases → Draft a new release** → seleccionar tag `v1.0.0`, pegar notas del CHANGELOG.

## Imagen Docker

Publicar imagen asociada al tag (ver [container-image.md](container-image.md)):

```bash
docker build -t ghcr.io/ghcetraro/doctor-ku:1.0.0 .
docker push ghcr.io/ghcetraro/doctor-ku:1.0.0
docker tag ghcr.io/ghcetraro/doctor-ku:1.0.0 ghcr.io/ghcetraro/doctor-ku:latest
docker push ghcr.io/ghcetraro/doctor-ku:latest
```

## Primera release pública

- **Tag:** `v1.0.0`
- **Fecha:** 2026-07-04
- **Imagen sugerida:** `ghcr.io/ghcetraro/doctor-ku:1.0.0`
