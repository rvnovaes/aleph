# Deploy de produção

Destino: alias SSH `aleph`, domínio `aleph.robertonovaes.com.br`.

Caddy no host termina TLS e encaminha para Nginx em `127.0.0.1:8088`.
Django e PostgreSQL não publicam portas. A rede Docker usa `172.30.88.0/24`;
o Nginx confia apenas no gateway `172.30.88.1` para o IP encaminhado pelo Caddy.
Não exponha o Nginx diretamente na internet.

## Requisitos e segredos

- Ansible no controlador e SSH funcional.
- `ansible-galaxy collection install -r deploy/ansible/requirements.yml`.
- GitHub CLI autenticado. Actions publica com seu próprio GITHUB_TOKEN.
- Variáveis locais em `deploy/.private/production.json`, permissão 0600; nunca versionadas.
- Variáveis: domain, registry_user, django_secret, postgres_password,
  production_login_password, backend_image, web_image, postgres_image, alpine_image.
- Imagens devem usar referências `nome@sha256:digest`; não usar latest.
- O token do controlador é utilizado apenas para pull em configuração Docker temporária
  no servidor, eliminada inclusive em caso de falha.
- O .env em produção tem permissão 0600. Não regenerar segredos em atualizações.

## Primeira instalação

1. `scripts/deploy-production.py prepare`
2. Commit/push dos fontes e `scripts/deploy-production.py publish --ref main`.
3. Acompanhe o workflow Production images. Use
   `scripts/pin-production-release.py <SHA-completo>` para selecionar as imagens aprovadas.
   Registre também digests das imagens PostgreSQL 16 e Alpine nas variáveis privadas.
4. `scripts/deploy-production.py stage` prepara banco e baixa imagens, sem abrir o site.
5. Faça backup consistente local: `scripts/backup.sh backups/production-migration`.
6. Valide: `scripts/check-restore.sh backups/production-migration`.
7. `scripts/deploy-production.py restore --backup backups/production-migration`.
8. `scripts/deploy-production.py deploy`.
9. Confira HTTPS, login, contagens, capas, downloads, importação e referências.

A restauração só opera sobre banco vazio e registra uma marca para impedir repetição.
Ela muda a senha de roberto somente em produção e elimina sessões locais copiadas.
Não reimporte o JSON: a migração leva o banco inteiro, mantendo IDs e revisões.

## Atualizações

Publique imagens de um commit testado, atualize apenas os digests e rode deploy.
O playbook faz backup, guarda o ambiente anterior, para a aplicação, aplica migrações
e aguarda verificações de saúde antes de validar HTTPS. Há uma breve indisponibilidade.
O acervo de produção não é sobrescrito pela máquina de desenvolvimento.

Em falha, inspecione `docker compose logs` em /opt/aleph. Para rollback de aplicação,
reutilize os digests de /opt/aleph/releases/previous.env com o banco compatível.
Se a migração não for retrocompatível, restaure explicitamente banco e arquivos do
backup correspondente; não reverta o banco automaticamente nem use down -v.

## Backups

- Timer do servidor: 06:00 UTC (03:00 em Brasília), retenção de 14 dias.
- Backup inclui pg_dump, mídia, ambiente e Compose; requer armazenamento privado.
- `scripts/fetch-production-backup.sh` copia via SSH para backups/production local.
- A cópia local é cumulativa, sem apagar backups já recebidos.
- A base local é preservada, mas passa a ser desenvolvimento após a migração.

Para agendar a cópia externa nesta estação:
`ansible-playbook deploy/ansible/backup-client.yml`.
O timer de usuário roda às 06:30 UTC e recupera execuções perdidas ao voltar.
A cópia depende desta máquina estar ligada, com sessão de usuário e SSH disponíveis.

Depois de um workflow aprovado, `scripts/pin-production-release.py <SHA-completo>`
atualiza os digests de backend/web nas variáveis privadas, sem tocar nos segredos.
O primeiro arquivo de variáveis deve conter também os digests PostgreSQL/Alpine.

## Instalação verificada em 30/10/2026

- Aplicação publicada em https://aleph.robertonovaes.com.br com TLS válido e redirecionamento HTTP.
- Release da aplicação: `5bfc43d6ee5ce79e267ffdd5243e85f11fdf9e76`; digests em `releases/`.
- Migrados 717 registros, 717 exemplares, 717 referências ABNT, 256 etiquetas e uma capa.
- Nenhum PDF existia na origem. A capa foi conferida por SHA-256.
- CI: 43 testes de backend e três testes de referências; verificação do frontend aprovada.
- Playwright em produção: login, cadastro, localização, ABNT editável e regenerada,
  otimização/ampliação de capa, envio, leitura e download de PDF aprovados.
- A conta temporária e seus dados foram removidos após o teste; contagens conferidas novamente.
- Login de roberto e cookies de sessão Secure/HttpOnly verificados.
- Senha de produção distinta da local, disponível somente em `deploy/.private/access.txt`.
