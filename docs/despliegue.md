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
  concurrencyPolicy: Forbid
  activeDeadlineSeconds: 1800
```

- **successfulJobsHistoryLimit / failedJobsHistoryLimit**: conserva las últimas 3 ejecuciones
- **concurrencyPolicy: Forbid**: no solapa ejecuciones
- **activeDeadlineSeconds**: timeout máximo por Job

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
