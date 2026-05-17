#!/usr/bin/env bash
# Build das imagens e deploy do Predicta em um cluster Kubernetes.
#
# Uso:
#   ./deploy/deploy.sh build     # apenas build das imagens
#   ./deploy/deploy.sh push      # push para o registry
#   ./deploy/deploy.sh deploy    # aplica os manifests no cluster
#   ./deploy/deploy.sh all       # build + deploy (padrao)
set -euo pipefail

# Executa sempre a partir da raiz do repositorio.
cd "$(dirname "$0")/.."

VERSION="${VERSION:-0.4.0}"
REGISTRY="${REGISTRY:-predicta}"
PUBLIC_API_URL="${PUBLIC_API_URL:-http://predicta.local}"
K8S_DIR="deploy/k8s"

build() {
  echo "==> Build das imagens (versao ${VERSION})"
  docker build -t "${REGISTRY}/backend:${VERSION}" \
    --build-arg PIP_EXTRAS="[rag]" ./backend
  docker build -t "${REGISTRY}/frontend:${VERSION}" \
    -f ./frontend/Dockerfile.prod \
    --build-arg NEXT_PUBLIC_API_URL="${PUBLIC_API_URL}" ./frontend
  docker build -t "${REGISTRY}/opcua-simulator:${VERSION}" ./edge/opcua_simulator
}

push() {
  echo "==> Push das imagens para ${REGISTRY}"
  docker push "${REGISTRY}/backend:${VERSION}"
  docker push "${REGISTRY}/frontend:${VERSION}"
  docker push "${REGISTRY}/opcua-simulator:${VERSION}"
}

deploy() {
  echo "==> Deploy no Kubernetes (namespace predicta)"
  kubectl apply -f "${K8S_DIR}/namespace.yaml"
  kubectl apply -f "${K8S_DIR}/databases.yaml"
  echo "--> Aguardando os bancos de dados..."
  kubectl -n predicta rollout status deploy/postgres --timeout=180s
  kubectl -n predicta rollout status deploy/timescaledb --timeout=180s
  echo "--> Aplicando o backend (Job de migracao + Deployment)"
  kubectl apply -f "${K8S_DIR}/backend.yaml"
  kubectl -n predicta wait --for=condition=complete job/predicta-migrate --timeout=240s
  kubectl apply -f "${K8S_DIR}/frontend.yaml"
  kubectl apply -f "${K8S_DIR}/ingress.yaml"
  kubectl -n predicta rollout status deploy/backend --timeout=240s
  kubectl -n predicta rollout status deploy/frontend --timeout=180s
  echo "==> Deploy concluido. Aponte 'predicta.local' para o Ingress Controller."
}

case "${1:-all}" in
  build) build ;;
  push) push ;;
  deploy) deploy ;;
  all) build && deploy ;;
  *) echo "Uso: $0 {build|push|deploy|all}" >&2; exit 1 ;;
esac
