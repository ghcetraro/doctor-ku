# Presentación — Doctor-ku

Material listo para publicar en **LinkedIn** (post + carrusel). Copiá cada sección como una diapositiva o bloque del post.

**Speech listo para copiar/pegar:** [speech-linkedin.md](speech-linkedin.md) — post principal, versiones corta/técnica/storytelling, script de video y primer comentario.

---

## Slide 1 — Hook

### ¿Tu cluster k3s se rompe y nadie está despierto?

Presento **Doctor-ku**: un monitor que detecta nodos caídos y los **reincorpora solo**.

Python · Kubernetes CronJob · Prometheus · SSH + API de K8s

---

## Slide 2 — El dolor

**Escenario real en bare-metal / homelab / on-prem:**

- Un master deja de estar `Ready`
- etcd conserva un miembro fantasma
- Reinstalar k3s a mano lleva 30–60 minutos
- Mientras tanto: menos capacidad, riesgo de perder quorum

**Automatizar esto no es lujo — es continuidad operativa.**

---

## Slide 3 — Qué hace Doctor-ku

```
┌─────────────┐     cada N min      ┌──────────────┐
│  CronJob    │ ─────────────────► │  Chequeo     │
│  (K8s)      │                    │  SSH + K8s   │
└─────────────┘                    └──────┬───────┘
                                          │
                    fallos ≥ umbral       ▼
                                   ┌──────────────┐
                                   │ Remediación  │
                                   │ · etcd       │
                                   │ · reinstall  │
                                   │ · verify     │
                                   └──────────────┘
```

- Monitorea **SSH**, **k3s** y **Ready** en Kubernetes
- Persiste contadores entre ejecuciones (PVC)
- Remedia nodos `NotReady` **y** `missing`

---

## Slide 4 — Remediación inteligente

Flujo automatizado:

1. Detectar nodo problemático (con umbral configurable)
2. Limpiar miembro etcd huérfano (masters HA)
3. Desinstalar y limpiar `/var/lib/rancher/k3s`
4. Reinstalar con **misma versión** del cluster (`get.k3s.io`)
5. Verificar servicio k3s + nodo `Ready` en K8s
6. Capturar `journalctl` si algo falla

**Un Job = una ejecución aislada.** También podés lanzarlo a mano.

---

## Slide 5 — Arquitectura en Kubernetes

| Componente | Rol |
|------------|-----|
| **CronJob** | Programa chequeos (`*/6 * * * *` o lo que definas) |
| **Job** | Ejecuta `python -m app.runner` y termina |
| **PVC** | Guarda estado y contadores de fallo |
| **Metrics Deployment** | Expone `/metrics` para Prometheus 24/7 |
| **Helm chart** | Todo empaquetado, listo para GitOps |

Historial: **últimas 3 ejecuciones** exitosas y fallidas.

---

## Slide 6 — Observabilidad

Métricas Prometheus incluidas:

- Estado por nodo: SSH, k3s, Ready
- Rachas de fallo consecutivas
- Contador de remediaciones (success / failed)
- Timestamp y resultado del último run

Compatible con **Grafana** — dashboards listos para armar alertas.

---

## Slide 7 — Stack técnico

| Capa | Tecnología |
|------|------------|
| App | Python 3.12, FastAPI, Pydantic |
| Conectividad | Paramiko (SSH), kubernetes client |
| Métricas | prometheus-client, exporter HTTP |
| Runtime | Kubernetes CronJob + Deployment |
| Empaquetado | Helm, Docker |
| Target | **k3s** (masters y workers) |

---

## Slide 8 — Diseño que aprendí construyéndolo

**Lecciones aplicadas en producción:**

- Un Deployment 24/7 no era ideal → **CronJob** con Jobs aislados
- El estado en memoria se pierde → **PVC** entre runs
- `delete node` sin reinstall deja nodos en limbo → detectar **`missing`**
- El install script puede “salir bien” sin arrancar k3s → **verificación + journal**
- Métricas de Jobs efímeros → **exporter persistente** (patrón push)

Open source. Configurable. Sin vendor lock-in.

---

## Slide 9 — Código abierto

**Doctor-ku** está disponible en GitHub.

Ideal para:

- Homelabs con k3s HA
- Clusters on-premise sin autoscaler
- Equipos que quieren **auto-healing** sin pagar un operador comercial
- Aprender automatización real de Kubernetes

⭐ Star · 🔀 Fork · 💬 Feedback bienvenido

---

## Slide 10 — CTA (llamada a la acción)

### ¿Tenés clusters k3s que mantenés vos mismo?

Doctor-ku puede ser tu **“doctor de guardia”** para nodos caídos.

🔗 Link al repo en GitHub (tu URL pública)

#kubernetes #k3s #devops #python #opensource #sre #homelab #prometheus #automation

---

## Texto sugerido para el post de LinkedIn

```
Llevaba tiempo queriendo automatizar algo que en k3s pasa seguido:
un nodo cae, queda NotReady o directamente desaparece del cluster,
y la recuperación manual (SSH + etcd + reinstall) es lenta y error-prone.

Así nació Doctor-ku 🩺

Es un monitor/remediador open source en Python que:
→ chequea nodos por SSH y la API de Kubernetes
→ corre como CronJob (cada ejecución es un Job aislado)
→ remedia automáticamente cuando hay fallos sostenidos
→ expone métricas Prometheus

Lo diseñé pensando en clusters bare-metal / on-prem / homelab
donde no tenés un cloud provider que te regenere nodos.

Stack: Python · k3s · Kubernetes CronJob · Helm · Prometheus

Código abierto — link en comentarios / bio.

¿Cómo manejan ustedes nodos caídos en k3s? Me interesa comparar enfoques.

#kubernetes #k3s #devops #opensource #python #sre #platformengineering
```

---

## Tips para el carrusel en LinkedIn

1. Exportá cada slide como imagen (1080×1080) con fondo oscuro y tipografía clara
2. Slide 1 = gancho visual con logo/nombre **Doctor-ku**
3. Slide 3 o 5 = diagrama de arquitectura ([docs/assets/architecture.svg](assets/architecture.svg) — exportar a PNG 1080×1080)
4. Slide 10 = CTA con QR o URL del repo
5. Publicá el post con el texto sugerido y adjuntá el PDF/carrusel
