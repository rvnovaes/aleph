# Entrega inicial — 30/10/2026

## Implementado

- Django/Ninja/PostgreSQL com migração inicial e autenticação por sessão/CSRF.
- SvelteKit estático, login, catálogo paginado, filtros, ficha editável e localizações.
- Livros/artigos, autoria ordenada, editora, cidade, periódico, ISBN/DOI, exemplares e PDFs.
- Identificadores validados; ISBN-10 convertido para ISBN-13; bloqueio de duplicidade por conta, com transação e trava no usuário.
- Cadastro contínuo mantém a localização; ficha já existente permite outro exemplar.
- Busca UFSC via YAZ/Z39.50 e interpretação de MARC, Open Library como alternativa; DOI via Crossref.
- Cache persistente, limite por fonte, timeouts e mensagens de indisponibilidade.
- Complementação preenche apenas campos vazios; resposta original selecionada fica armazenada.
- PDF com validação estrutural, limite de 100 MB, hash, download autenticado e leitor embutido do navegador.
- CSL-JSON e referências com citeproc-js/IBICT ABNT, estilo de 26/03/2026 incluído no repositório.
- Backup coordenado de banco/PDFs e teste de restauração em banco temporário.

## Evidências

1. Backend: **14 testes passaram em PostgreSQL 16**, incluindo autorização, CSRF, isolamento, normalização, duplicidade, PDF, fallback/cache, conversão CSL, limite de login e catálogo com 15.000 registros sintéticos.
2. Frontend: `svelte-check` sem erros ou avisos; build estático concluído.
3. Referências: três testes passaram para livro, artigo com DOI e organizador/tradutor. Testes verificam componentes importantes; não equivalem a uma certificação normativa de todos os formatos.
4. Navegador Chrome/Playwright: login → localização → livro com autor → exemplar → PDF → download → leitor → referência → busca → logout. Sem erros JavaScript capturados.
5. UFSC real: ISBN `9788535914849` retornou dois registros de **1984**, George Orwell, ano 2009. Confirmada conexão ao servidor Z39.50 e recuperação/normalização MARC.
6. Open Library real: ISBN `9780140328721` retornou **Fantastic Mr. Fox**, 1988.
7. Crossref real: DOI `10.1038/nphys1170` retornou **Measured measurement**, 2009.
8. Backup de teste: dump restaurado em banco descartável com dois registros de teste e um PDF. Hash do PDF restaurado conferiu. Backend voltou a funcionar após a captura.
9. As contas e os arquivos temporários de validação foram removidos do acervo ativo. Usuário `roberto` preservado, aguardando definição de senha.

## Achado de interoperabilidade

O servidor UFSC recusa `show 1+5` quando há menos de cinco resultados. O conector primeiro lê a contagem e só então pede até cinco registros. A busca considera ISBN-13 e ISBN-10 equivalente. Um teste de regressão verifica a contagem solicitada. Não se interpreta uma falha de recuperação como ausência de resultados.

## Operação e limites

Aplicação local em http://localhost:8088. O usuário deve executar `./scripts/set-password.sh roberto` para definir sua senha.

O volume compartilhado possui diretórios separados; backend usa UID 1000 e PostgreSQL mantém os arquivos internos com suas próprias permissões. Não há armazenamento dos bytes de PDF em colunas SQL.

O leitor é o nativo do navegador, não uma aplicação PDF.js própria. Referências são copiadas em texto simples. Extração automática de dados de PDFs, OCR, busca externa por título/autor, compartilhamento e importação MARC em massa não fazem parte desta entrega.

O teste com 15 mil registros valida funcionamento e paginação, não representa medição formal de desempenho com todo o acervo real. Próximo passo: cadastrar uma prateleira real e avaliar cobertura das fontes, qualidade dos nomes e produtividade do fluxo.
