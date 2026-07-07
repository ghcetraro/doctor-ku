# Despliegue en Kubernetes

Doctor-ku corre como **CronJob**: cada ejecución es un Job aislado que chequea todos los clusters configurados y termina.

## Componentes Helm

| Recurso | Descripción |
|---------|-------------|
| `CronJob` | Programa las ejecuciones (`cron.schedule`) |
| `Deployment` (metrics) | Expone `/metrics` y `/health` de forma persistente |
| `Service` | Puerto 8080 para Prometheus |
| `Ingress` (opcional) | Exponer métricas externamente |
| `PersistentVolumeClaim` | Persiste contadores de fallo y último resultado |
| `ConfigMap` | Configuración de clusters |
| `Secret` | Claves SSH (vía `secrets.yaml`, no commitear) |

## Secretos

```bash
cp helm/secrets.example.yaml helm/secrets.yaml
# Editar helm/secrets.yaml con tu clave SSH

helm upgrade --install doctor-ku ./helm \
  -f helm/values-production.yaml \
  -f helm/secrets.yaml \
  -n doctor-ku --create-namespace
```

## Configuración del CronJob

```yaml
cron:
  enabled: true
  schedule: "0 */6 * * *"
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  concurrencyPolicy: Replace
  activeDeadlineSeconds: 1800
  runTimeoutSeconds: 1500
```

- **successfulJobsHistoryLimit / failedJobsHistoryLimit**: conserva las últimas 3 ejecuciones
- **concurrencyPolicy: Replace**: si un Job anterior sigue activo, el siguiente ciclo lo cancela y crea uno nuevo (evita bloqueos prolongados con `Forbid`)
- **activeDeadlineSeconds**: timeout máximo del Job en Kubernetes (30 min)
- **runTimeoutSeconds**: timeout interno de la app (`RUN_TIMEOUT_SECONDS`, 25 min), por debajo del deadline del Job

El scheduler de Kubernetes elige cualquier nodo **Ready** y con recursos disponibles; no hay `nodeSelector` fijo.

## Job colgado o sin logs (502 kubelet)

Síntoma típico al ver logs:

```text
Get "https://<nodo>:10250/containerLogs/...": proxy error ... code 502: 502 Bad Gateway
```

Eso indica que el pod del Job estaba en un nodo con kubelet inaccesible. Con `concurrencyPolicy: Forbid`, el CronJob no crea ejecuciones nuevas mientras ese Job figure activo.

### Recuperación inmediata

```bash
# Ver jobs activos
kubectl -n doctor-ku get jobs -l app.kubernetes.io/name=doctor-ku

# Borrar el job colgado (reemplazar por el nombre real)
kubectl -n doctor-ku delete job doctor-ku-12345678

# Si el pod queda en Terminating por nodo caído, forzar borrado
kubectl -n doctor-ku delete pod doctor-ku-12345678-abcd1 --force --grace-period=0

# Disparar una ejecución manual
kubectl -n doctor-ku create job doctor-ku-manual-$(date +%s) --from=cronjob/doctor-ku
```

Si no hay logs, revisar en qué nodo estaba el pod:

```bash
kubectl -n doctor-ku get pod -l app.kubernetes.io/name=doctor-ku -o wide
```

### Prevención (ya en el chart)

| Medida | Efecto |
|--------|--------|
| Scheduler por defecto | El pod va a cualquier nodo Ready con capacidad |
| `concurrencyPolicy: Replace` | El cron siguiente reemplaza un Job atascado |
| `activeDeadlineSeconds: 1800` | Kubernetes marca el Job como fallido tras 30 min |
| `RUN_TIMEOUT_SECONDS: 1500` | La app sale antes que el deadline del Job |
| `ttlSecondsAfterFinished: 3600` | Limpia Jobs terminados tras 1 h |

## Ejecución manual

```bash
kubectl -n doctor-ku create job doctor-ku-manual-$(date +%s) \
  --from=cronjob/doctor-ku
```

Ver logs:

```bash
kubectl -n doctor-ku logs -l app.kubernetes.io/name=doctor-ku --tail=200
kubectl -n doctor-ku get jobs -l app.kubernetes.io/name=doctor-ku
```

## Estado persistido

Entre ejecuciones se guarda en el PVC (`/data/state.json`):

- Contadores de fallos consecutivos
- Último resultado por cluster
- Timestamp del último run

## Métricas

El CronJob publica métricas al exporter vía `POST /internal/update`.
Prometheus scrapea el Service del exporter en `/metrics`.

## Local

```bash
docker compose run --rm -v doctor-ku-data:/data doctor-ku python -m app.runner
```

Modo API HTTP (desarrollo):

```bash
docker compose run --rm -p 8089:8080 doctor-ku \
  uvicorn app.main:app --host 0.0.0.0 --port 8080
```
