# Seguridad

## Secretos

**Nunca commitees** al repositorio:

- Claves privadas SSH
- Tokens de cluster k3s
- Kubeconfig con credenciales
- URLs de webhooks con tokens embebidos
- Credenciales de registry

## Configuración recomendada

1. Copiá `helm/secrets.example.yaml` → `helm/secrets.yaml` (gitignored)
2. Montá claves SSH solo en el cluster vía Helm `-f secrets.yaml`
3. Preferí **External Secrets**, **Sealed Secrets** o **SOPS** en producción
4. Rotá claves SSH periódicamente
5. Usá un usuario SSH dedicado con sudo limitado en nodos k3s

## Permisos SSH en nodos

El usuario configurado (`ssh_user`) necesita típicamente:

- `systemctl` sobre k3s / k3s-agent
- Ejecutar scripts de install/uninstall (sudo)
- Leer kubeconfig y token en masters (`/etc/rancher/k3s/`, `/var/lib/rancher/k3s/`)

Restringí acceso por clave pública y firewall.

## Reporte de vulnerabilidades

Si encontrás un problema de seguridad, abrí un issue privado o contactá al mantenedor del repo.
