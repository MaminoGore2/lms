# lms-infra

Инфраструктура учебного проекта LMS (образовательная платформа):
- Kubernetes-кластер локально (k3d / k3s в Docker)
- PostgreSQL (Bitnami Helm chart)
- S3-совместимое хранилище MinIO (официальный Helm chart)
- Создание пользователя БД для приложения и бакетов MinIO


## Требования
- Ubuntu 22.04+ (можно в виртуальной машине)
- Docker Engine (работает команда docker ps)
- kubectl
- helm
- k3d

Рекомендуемые ресурсы VM: 6–8 ГБ ОЗУ, 4 CPU, 40+ ГБ диск.

## Быстрый старт
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/lms-infra.git
cd lms-infra

cp .env.example .env
nano .env   # или любой редактор, заполнить пароли

chmod +x scripts/*.sh

bash scripts/00-check.sh
bash scripts/10-cluster-create.sh
bash scripts/20-infra-install.sh
bash scripts/30-postinstall.sh
