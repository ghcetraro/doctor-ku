# Imagen Docker (GHCR)

Imagen publicada recomendada: **GitHub Container Registry** (`ghcr.io`).

## Build local

```bash
docker build -t doctor-ku:local .
docker run --rm \
  -v "$(pwd)/config/clusters.example.yaml:/config/clusters.yaml:ro" \
  -v "$(pwd)/secrets/ssh:/secrets/ssh:ro" \
  doctor-ku:local
```

## Publicar en GHCR

Requisitos: cuenta GitHub, token con permiso `write:packages` (PAT o `GITHUB_TOKEN` en Actions).

### Login

```bash
echo "$GITHUB_TOKEN" | docker login ghcr.io -u ghcetraro --password-stdin
```

### Build y push

Reemplazá `1.0.0` por la versión del [CHANGELOG](../CHANGELOG.md):

```bash
export VERSION=1.0.0
export IMAGE=ghcr.io/ghcetraro/doctor-ku

docker build -t "${IMAGE}:${VERSION}" .
docker push "${IMAGE}:${VERSION}"

docker tag "${IMAGE}:${VERSION}" "${IMAGE}:latest"
docker push "${IMAGE}:latest"
```

### Visibilidad del paquete

Tras el primer push, en GitHub → **Packages** → `doctor-ku` → **Package settings** → cambiar a **Public** si querés que otros hagan pull sin autenticación.

## Usar la imagen en Helm

```yaml
base:
  deployment:
    ecr: ghcr.io/ghcetraro
    image: doctor-ku
    tag: "1.0.0"
    pullPolicy: IfNotPresent

  imagePullSecrets:
    enabled: false   # true solo si el paquete es private
```

Si el paquete es **private**, creá un secret en el cluster:

```bash
kubectl create secret docker-registry ghcr-login \
  --docker-server=ghcr.io \
  --docker-username=ghcetraro \
  --docker-password="$GITHUB_TOKEN" \
  -n doctor-ku
```

Y en values:

```yaml
base:
  imagePullSecrets:
    enabled: true
    name: ghcr-login
```

## CI (GitHub Actions)

El workflow [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) valida build y sintaxis en cada push/PR.
Opcional: agregar un workflow de release que construya y publique en GHCR al pushear tags `v*`.

## Multi-arch (opcional)

```bash
docker buildx build --platform linux/amd64,linux/arm64 \
  -t ghcr.io/ghcetraro/doctor-ku:1.0.0 --push .
```

Útil para clusters ARM (Raspberry Pi, etc.).
