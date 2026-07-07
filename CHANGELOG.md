# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).
Versionado según [Semantic Versioning](https://semver.org/lang/es/).

## [1.0.1] - 2026-07-07

### Changed

- CronJob: `concurrencyPolicy: Replace` para evitar bloqueos cuando un Job queda colgado
- Timeout global de ejecución (`RUN_TIMEOUT_SECONDS`, default 1500 s)
- `ttlSecondsAfterFinished` reducido a 3600 s (1 h)
- Documentación de recuperación ante error 502 del kubelet

## [1.0.0] - 2026-07-04

Primera release pública.

### Added

- Monitor de nodos k3s por SSH y API de Kubernetes
- Remediación automática: uninstall, limpieza, reinstall vía `get.k3s.io`
- Soporte para nodos `NotReady` y `missing` (ausentes del cluster)
- Limpieza de miembros etcd fantasma en masters HA
- Ejecución como Kubernetes CronJob con Jobs aislados
- Estado persistente en PVC (`failure_threshold` entre runs)
- Exporter de métricas Prometheus (`doctorku_*`)
- Helm chart (CronJob, PVC, metrics Deployment, Service, Ingress opcional)
- Modo runner local (`python -m app.runner`) y docker-compose
- Documentación de despliegue, remediación y presentación LinkedIn

### Security

- Claves SSH fuera del repositorio (`helm/secrets.yaml` gitignored)

[1.0.1]: https://github.com/ghcetraro/doctor-ku/releases/tag/v1.0.1
[1.0.0]: https://github.com/ghcetraro/doctor-ku/releases/tag/v1.0.0
