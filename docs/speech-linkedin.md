# Speech para LinkedIn — Doctor-ku

Documento listo para publicar. Copiá el bloque que prefieras, pegá el link del repo en el **primer comentario** (LinkedIn premia más el engagement que links en el cuerpo del post).

**Repo:** `https://github.com/ghcetraro/doctor-ku`

**Diagrama para carrusel:** `docs/assets/architecture.svg` (exportar a PNG 1080×1080)

---

## Post breve (con link)

Versión corta para publicar directo. Incluye el link al repo en el cuerpo del post.

```
Publiqué Doctor-ku 🩺 — monitor y remediador automático para clusters k3s.

Detecta nodos caídos (SSH + API de Kubernetes) y los reincorpora solo cuando hay fallos sostenidos. Corre como CronJob, con métricas Prometheus.

Open source · Python · Helm

🔗 https://github.com/ghcetraro/doctor-ku

#kubernetes #k3s #devops #opensource #python
```

**Alternativa** (si LinkedIn limita alcance con link en el post — link en primer comentario):

Post:
```
Publiqué Doctor-ku 🩺 — monitor y remediador automático para clusters k3s.

Detecta nodos caídos y los reincorpora solo. CronJob + Prometheus. Open source en Python.

Link en el primer comentario 👇

#kubernetes #k3s #devops #opensource
```

Comentario:
```
https://github.com/ghcetraro/doctor-ku
```

---

## Post principal (recomendado)

Usá este para el lanzamiento open source con carrusel o imagen del diagrama.

```
Llevaba tiempo queriendo automatizar algo que en k3s pasa seguido:

un nodo cae, queda NotReady o directamente desaparece del cluster…
y la recuperación manual (SSH + etcd + reinstall) es lenta, repetitiva y fácil de hacer mal.

Así nació Doctor-ku 🩺

Es un monitor y remediador open source en Python que:

→ chequea nodos por SSH y la API de Kubernetes
→ corre como CronJob (cada ejecución es un Job aislado)
→ remedia automáticamente cuando hay fallos sostenidos
→ expone métricas Prometheus para alertas y dashboards

Lo diseñé para clusters bare-metal, on-prem y homelab
donde no tenés un cloud provider que te regenere nodos por vos.

Stack: Python · k3s · Kubernetes CronJob · Helm · Prometheus

Código abierto — link en el primer comentario 👇

¿Cómo manejan ustedes nodos caídos en k3s? Me interesa comparar enfoques.

#kubernetes #k3s #devops #opensource #python #sre #platformengineering #homelab #prometheus
```

### Primer comentario (pegá esto apenas publiques)

```
🔗 Doctor-ku en GitHub:
https://github.com/ghcetraro/doctor-ku

MIT · Helm chart incluido · métricas Prometheus · documentación en español

Si te sirve, una ⭐ ayuda mucho 🙌
```

---

## Versión corta (sin carrusel)

Para un post rápido con una sola imagen (diagrama o captura de métricas).

```
Publiqué Doctor-ku 🩺 — monitor y remediador automático para clusters k3s.

Cuando un nodo queda NotReady o desaparece del cluster, el tool:
· detecta el fallo por SSH + API de K8s
· acumula intentos entre ejecuciones
· reinstala y reincorpora el nodo si supera el umbral

Corre como CronJob, con estado en PVC y métricas Prometheus.

Open source en Python. Pensado para bare-metal / homelab / on-prem.

Link en comentarios 👇

#kubernetes #k3s #devops #python #opensource
```

---

## Versión storytelling (más personal)

Ideal si querés contar el origen del proyecto.

```
A las 2 de la mañana no querés hacer SSH para reinstalar k3s.

Eso me pasó más de una vez: un master caído, etcd con un miembro fantasma,
30–60 minutos de manual work, y al día siguiente el mismo problema otra vez.

Decidí automatizarlo de verdad.

Doctor-ku es el resultado: un “doctor de guardia” para clusters k3s.

No es magia — es un CronJob en Kubernetes que:
1. Monitorea SSH, servicio k3s y estado Ready del nodo
2. Guarda contadores de fallo entre ejecuciones (PVC)
3. Cuando hay fallos sostenidos, limpia etcd, desinstala, reinstala con la misma versión del cluster y verifica que el nodo vuelva a Ready
4. Publica métricas para Prometheus

Lo construí en Python, empaquetado con Helm, con CI y documentación lista para quien quiera probarlo en homelab o producción on-prem.

Está en GitHub (MIT). Link abajo.

Si mantenés k3s sin autoscaler de cloud, capaz te ahorra una madrugada.

¿Alguna vez tuvieron que remediar un nodo k3s a mano? Cuéntenme 👇

#kubernetes #k3s #devops #sre #opensource #python #platformengineering #homelab
```

---

## Versión técnica (para audiencia SRE / Platform)

```
Doctor-ku — auto-healing para nodos k3s en bare-metal

Problema: nodos NotReady o missing sin autoscaler → remediación manual (etcd cleanup + reinstall + verify).

Solución:
· CronJob → Job aislado por run (`python -m app.runner`)
· Estado persistente en PVC (failure streak entre ciclos)
· Remediación: remove etcd ghost member → k3s-uninstall → rm /var/lib/rancher/k3s → get.k3s.io (misma versión) → verify systemctl + node Ready
· Nodos `missing` incluidos (no solo NotReady)
· Metrics Deployment 24/7 + push desde el Job (`doctorku_*` para Prometheus/Grafana)
· Helm chart, dry_run, max_nodes_per_cycle

Stack: Python 3.12 · Paramiko · kubernetes client · prometheus-client

Repo: comentario 👇 · MIT

Feedback de quienes operen k3s HA bienvenido.

#kubernetes #k3s #sre #devops #prometheus #opensource #python #platformengineering
```

---

## Script para video / reel (60–90 segundos)

Leé esto mirando a cámara o grabando pantalla con el diagrama.

```
[0–10 s — gancho]
¿Tenés un cluster k3s y un nodo que se cae cuando nadie está despierto?
Eso es exactamente lo que Doctor-ku resuelve.

[10–25 s — problema]
En bare-metal o homelab, cuando un master queda NotReady o desaparece del cluster,
recuperarlo a mano significa SSH, limpiar etcd, reinstalar k3s y verificar que vuelva a Ready.
Eso puede llevar una hora. Y duele si pasa de madrugada.

[25–50 s — solución]
Doctor-ku es un monitor open source en Python que corre como CronJob en Kubernetes.
Cada X minutos hace un chequeo por SSH y por la API de K8s.
Si un nodo falla varias veces seguidas, lo remedia solo:
limpia el miembro fantasma en etcd, reinstala k3s con la versión correcta
y confirma que el nodo esté Ready otra vez.
Además expone métricas para Prometheus.

[50–70 s — para quién]
Lo pensé para quien opera k3s sin autoscaler de cloud:
homelab, on-prem, infra propia.

[70–90 s — cierre]
Está en GitHub, licencia MIT, con Helm chart y documentación.
Link en la descripción.
Si te sirve, dejame un comentario contando cómo manejan ustedes nodos caídos en k3s.
```

**Texto para descripción del video:**

```
Doctor-ku — monitor y remediador automático para clusters k3s (open source)
🔗 https://github.com/ghcetraro/doctor-ku
Python · CronJob · Helm · Prometheus
#kubernetes #k3s #devops #opensource
```

---

## Speech para carrusel (narración slide a slide)

Si grabás un carrusel con voz en off o querés subtítulos:

| Slide | Texto |
|-------|--------|
| 1 | ¿Tu cluster k3s se rompe y nadie está despierto? Conocé Doctor-ku. |
| 2 | Un master NotReady. etcd con un miembro fantasma. Reinstalar a mano: 30 a 60 minutos. |
| 3 | Doctor-ku monitorea por SSH y Kubernetes. Si hay fallos sostenidos, remedia solo. |
| 4 | Limpia etcd, desinstala k3s, reinstala con la misma versión y verifica que el nodo vuelva a Ready. |
| 5 | Corre como CronJob. Estado en PVC. Métricas Prometheus 24/7. Todo empaquetado en Helm. |
| 6 | Métricas por nodo: SSH, k3s, Ready, rachas de fallo, remediaciones exitosas o fallidas. |
| 7 | Python 3.12, Paramiko, kubernetes client, prometheus-client. Target: k3s. |
| 8 | Lecciones reales: Jobs aislados, estado persistente, nodos missing, verificación post-install. |
| 9 | Open source. MIT. Ideal para homelab, on-prem y equipos sin operador comercial. |
| 10 | Link en GitHub. Doctor-ku: tu doctor de guardia para nodos k3s. ⭐ si te sirve. |

---

## Preguntas para generar comentarios

Publicá una de estas al final del post o como comentario propio para impulsar conversación:

1. ¿Cómo detectan hoy un nodo k3s caído — alertas, uptime externo, o “cuando algo deja de andar”?
2. ¿Alguna vez perdieron quorum en etcd por un master que no volvió solo?
3. ¿Usan algo comercial para auto-healing o todo es runbook manual?
4. ¿Qué les parece más riesgoso: remediación automática o depender de intervención humana a las 3 AM?

---

## Hashtags alternativos

**Set A (amplio):** `#kubernetes #k3s #devops #opensource #python #sre`

**Set B (homelab):** `#homelab #selfhosted #k3s #kubernetes #devops #opensource`

**Set C (observabilidad):** `#prometheus #grafana #observability #kubernetes #k3s #sre`

Usá 5–8 hashtags como máximo; LinkedIn penaliza el exceso.

---

## Checklist antes de publicar

- [ ] Repo público en GitHub con README y diagrama
- [ ] Link en **primer comentario**, no solo en el post
- [ ] Imagen o carrusel adjunto (diagrama `architecture.svg` exportado a PNG)
- [ ] Revisar que no haya IPs, hostnames ni secretos en capturas
- [ ] Responder comentarios en las primeras 2 horas (alcance orgánico)
- [ ] Opcional: taggear a colegas que operen k3s (con permiso)

---

## Material relacionado

- Carrusel slide a slide: [PRESENTACION.md](PRESENTACION.md)
- README del proyecto: [../README.md](../README.md)
