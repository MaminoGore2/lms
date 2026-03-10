```md
# Runbook: развёртывание инфраструктуры LMS локально (k3d)

## 1. Предусловия
Должны быть установлены и работать:
- Docker Engine: docker ps без ошибок
- kubectl: kubectl version --client
- Helm: helm version
- k3d: k3d version

Рекомендуемые ресурсы для виртуальной машины:
- ОЗУ 6–8 ГБ
- CPU 4
- Диск 40–60 ГБ

## 2. Подготовка проекта
1) Клонировать репозиторий:
```bash
git clone https://github.com/<YOUR_GITHUB_USERNAME>/lms-infra.git
cd lms-infra
