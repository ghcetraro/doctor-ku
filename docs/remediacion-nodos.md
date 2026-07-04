# Remediación de nodos k3s

Doctor-ku monitorea nodos k3s por SSH y API de Kubernetes, y remedia automáticamente cuando detecta fallos sostenidos.

## Cuándo remedia

| Estado en K8s | SSH | Acción |
|---------------|-----|--------|
| `NotReady` | OK | Tras `failure_threshold` ciclos consecutivos |
| `missing` (404) | OK | Tras `failure_threshold` ciclos consecutivos |
| `Ready` | OK | Resetea contador de fallos |
| Cualquiera | caído | No remedia |

Un nodo `missing` está configurado en YAML pero ausente del cluster (típico tras un delete parcial).

## Flujo de remediación

1. **pre_remediation** (opcional)
2. **delete node** en K8s — omitido si el nodo ya está `missing`
3. **etcd cleanup** (masters) — elimina miembro fantasma desde un master sano
4. **uninstall** + limpieza de `/var/lib/rancher/k3s`
5. **install** vía `curl get.k3s.io` con `INSTALL_K3S_FORCE_RESTART=true`
6. **verify** servicio k3s activo y nodo `Ready` en K8s
7. Si falla: captura `journalctl -u k3s` en el resultado

## Recuperación manual

Si la remediación automática falla:

### 1. Diagnóstico

```bash
kubectl -n doctor-ku logs -l app.kubernetes.io/name=doctor-ku --tail=200
```

### 2. Snapshot etcd (desde un master sano)

```bash
ssh deploy@192.168.1.101
sudo k3s etcd-snapshot save --name pre-recovery-$(date +%s)
```

### 3. Eliminar miembro etcd fantasma

```bash
export ETCDCTL_API=3
sudo apt-get install -y etcd-client  # si no está instalado

sudo env ETCDCTL_API=3 etcdctl --endpoints=https://127.0.0.1:2379 \
  --cacert=/var/lib/rancher/k3s/server/tls/etcd/server-ca.crt \
  --cert=/var/lib/rancher/k3s/server/tls/etcd/client.crt \
  --key=/var/lib/rancher/k3s/server/tls/etcd/client.key \
  member list -w table

# Reemplazar <MEMBER_ID> con el ID del nodo afectado
sudo env ETCDCTL_API=3 etcdctl ... member remove <MEMBER_ID>
```

### 4. Reinstalar k3s en el nodo afectado

```bash
ssh deploy@192.168.1.102
sudo systemctl stop k3s || true
sudo /usr/local/bin/k3s-uninstall.sh || true

export MI_TOKEN="<token-del-cluster>"
export INSTALL_K3S_VERSION="v1.34.3+k3s1"  # misma versión que el cluster

curl -sfL https://get.k3s.io | K3S_TOKEN=$MI_TOKEN sh -s - server \
  --server https://192.168.1.101:6443
```

### 5. Verificar

```bash
sudo systemctl status k3s
sudo k3s kubectl get nodes -o wide
```

## Placeholders en comandos de install

| Placeholder | Origen |
|-------------|--------|
| `{{K3S_TOKEN}}` | Token desde nodo sano |
| `{{BOOTSTRAP_SERVER}}` | URL del API server en kubeconfig |
| `{{K3S_VERSION}}` | `k3s --version` en nodo sano |
| `{{NODE_NAME}}` | Nombre en config |
| `{{NODE_HOST}}` | IP del nodo en config |
