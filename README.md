# Aleph — biblioteca pessoal

Catálogo privado de livros e artigos com localização de exemplares, cadastro assistido por ISBN/DOI, arquivos PDF e referências ABNT.

## Iniciar

```bash
cp .env.example .env  # somente em instalação nova; preserve o .env existente
# Defina SECRET_KEY e POSTGRES_PASSWORD com valores aleatórios diferentes.
docker compose up -d --build
docker compose exec backend python manage.py createsuperuser
```

Abra http://localhost:8088 e entre com o usuário criado acima. Para trocar a senha de um usuário existente:

```bash
./scripts/set-password.sh roberto
```

O serviço está vinculado apenas ao localhost. Para exposição em rede, configure HTTPS, hosts permitidos e `COOKIE_SECURE=1`. Não há inscrição pública.

## Catalogar uma prateleira

1. Cadastre ambiente, estante e prateleira em **Localizações**.
2. Abra **Cadastrar livro ou artigo**, selecione a localização e adicione um **ISBN**. Digite ou leia o código com um leitor que funciona como teclado; use **Buscar dados** ou Enter.
3. Escolha uma ficha retornada pela UFSC ou Open Library e confira seus dados.
4. **Salvar e cadastrar próximo** mantém a localização escolhida.
5. Se o ISBN já existir, adicione outro exemplar ao registro existente.
6. Sem resultado externo, complete os campos ou salve como pendente.

Para artigos, selecione DOI. O conector Crossref preenche os dados disponíveis. A consulta pode falhar sem impedir o cadastro manual. A busca externa valida ISBN/DOI, usa cache de sete dias e um intervalo mínimo entre chamadas por fonte. ISBN-10 e ISBN-13 equivalentes são normalizados para o mesmo valor.

Em uma ficha existente, **Buscar dados faltantes** preenche apenas campos vazios. Valores existentes são preservados. O original selecionado fica vinculado ao registro em `SourceRecord`.

## PDFs

Salve a ficha e envie um PDF de até 100 MB. Há leitura embutida pelo visualizador PDF do navegador, abertura em nova aba e download autenticado. PDFs criptografados, vazios ou inválidos são rejeitados. O mesmo arquivo enviado novamente à mesma ficha é reutilizado.

Banco e arquivos compartilham o volume Docker `aleph_library`: `pgdata/` pertence ao PostgreSQL e `pdfs/` ao backend. PDFs não são servidos como arquivos públicos. O backend roda sem privilégios de root e sem permissão de leitura dos arquivos internos do banco.

## ABNT

Usa citeproc-js, CSL-JSON e o estilo **IBICT — ABNT (autoria completa)**, atualização declarada em **26/03/2026**, mantido no repositório CSL usado pelo Zotero. Estilo e locale estão incluídos, sem consulta externa ao gerar referências. Veja [atribuição e versões](docs/THIRD_PARTY.md).

Confira prenomes/sobrenome e dados de publicação: nenhuma fonte garante metadados completos. A cópia inicial é texto simples; itálicos/negritos não são preservados no clipboard nesta versão. Não inclui plugin para Word ou inserção de citações em textos.

## Backup e verificação

```bash
./scripts/backup.sh
./scripts/check-restore.sh backups/AAAAmmdd-HHMMSS
```

O backup pausa o backend durante a captura para manter banco e arquivos consistentes; reinicia ao terminar. A verificação restaura o dump em uma base temporária, extrai os PDFs e compara seus hashes. Mantenha cópias fora deste disco. Nunca use `docker compose down -v` se quiser preservar o acervo.

Para recuperação efetiva, em uma instalação vazia: inicie `db` e `storage-init`, restaure o dump com `pg_restore`, extraia `pdfs/` no volume e só então inicie backend/web. Não restaure sobre uma base em uso sem um backup prévio.

## Desenvolvimento e testes

```bash
docker compose exec -T backend pytest -q -p no:cacheprovider
cd frontend
npm ci
npm run check
npm run build
node tests/citations.test.mjs
```

API/OpenAPI: `/api/v1/docs` (login necessário). Especificação: `/api/v1/openapi.json`.

Teste de navegador com conta temporária:

```bash
docker compose exec -T backend python manage.py prepare_e2e
docker compose cp backend:/tmp/aleph-e2e.json /tmp/aleph-e2e.json
docker compose cp backend:/tmp/aleph-e2e.pdf /tmp/aleph-e2e.pdf
docker compose cp backend:/tmp/aleph-e2e-cover.jpg /tmp/aleph-e2e-cover.jpg
cd frontend
npx playwright test
```

O teste usa Chrome em `/usr/bin/google-chrome`; altere `PLAYWRIGHT_EXECUTABLE_PATH` se necessário. As credenciais temporárias ficam em `/tmp`, nunca no repositório. Não use a conta de teste como conta pessoal.

## Limites desta entrega

- Um catálogo privado por usuário; compartilhamento entre usuários não implementado.
- Cada edição é uma ficha própria; não há hierarquia abstrata de obras/expressões.
- Consulta externa por ISBN/DOI; consulta externa por título e importação MARC em massa ficam para evolução.
- Leitura de PDF usa o leitor do navegador; não há OCR, extração automática de ISBN/DOI ou anotações.
- Autores não são fundidos automaticamente entre fichas; editar a mesma ficha reutiliza os autores inalterados.
- Testes de escala usam dados sintéticos; o piloto com seus livros ainda precisa ser realizado.

Stack: Django 5.2, Django Ninja, PostgreSQL 16, SvelteKit/Svelte 5, Tailwind, Nginx e Docker Compose.

## Capas

Na ficha salva, use **Capa → Enviar ou substituir capa**. Entradas aceitas: JPEG/PNG estáticos de até 10 MB e 20 megapixels. Pillow corrige a orientação EXIF, reduz preservando a proporção (sem ampliar imagens pequenas) e centraliza em uma tela branca de **600 × 900 pixels**. A saída é **WebP, qualidade 82**, sem EXIF ou outros metadados do original.

Somente o WebP processado é persistido. O original passa pelo upload temporário da requisição e não é guardado no acervo. Substituir ou remover uma capa elimina o arquivo anterior após a transação concluir. Capas exigem login e pertencem ao usuário do registro.

Os arquivos ficam em `pdfs/covers/` dentro do volume existente, sendo incluídos no backup de mídia atual. A imagem aparece na ficha e como miniatura no catálogo. O envio de capa preserva alterações ainda não salvas nos campos bibliográficos.

## Navegar pelas localizações

Em **Localizações**, escolha um ambiente, depois uma estante e uma prateleira. Cada nível mostra os títulos presentes e permite buscar dentro daquele recorte. Os cartões distinguem títulos de exemplares: duas cópias do mesmo livro contam como dois exemplares e um título. Abra uma ficha e use **Voltar à localização** para continuar de onde parou. O formulário para cadastrar novos lugares permanece abaixo do navegador.

## Importar LibraryThing

Execute `./scripts/import-librarything.sh data/arquivo.json roberto --dry-run` para simular e retire `--dry-run` para importar. Faça backup antes com `./scripts/backup.sh backups/pre-import`. O script grava um relatório JSON em `docs/`. Cada registro original é preservado; repetir a importação ignora IDs já importados e mantém as edições manuais.

Etiquetas pessoais, assuntos, CDD/LCC, série, título/idioma original, descrição física e publicação ficam na ficha. Código antigo, aquisição, conservação e valores ficam no exemplar. O campo genérico `price` entra como **Valor informado**, separado de preço de compra e valor estimado. A moeda BRL é assumida: o arquivo não a declara. Livros sem localização ficam disponíveis no filtro **Exemplares sem localização**.

## Identidade visual e tema

O logo da entrada e o símbolo do cabeçalho/aba usam os arquivos fornecidos em `data/`, publicados em `frontend/static/`. A paleta combina creme, dourado e carvão. O botão **Modo claro / Modo escuro** fica no cabeçalho, inclusive antes do login; a escolha é salva neste navegador. Sem escolha anterior, segue o tema do sistema.

Para completar **cidade e editora** em registros já importados, use:

```bash
./scripts/import-librarything.sh data/librarything_rvnovaes_202610301505.json roberto --repair-publication --dry-run
./scripts/import-librarything.sh data/librarything_rvnovaes_202610301505.json roberto --repair-publication
```

A reparação separa a publicação no formato “Cidade: Editora”, preenche apenas relações vazias e registra os campos preenchidos no relatório. Não modifica exemplares, capas, preços, anotações nem o JSON original. Registros cujo conteúdo de origem mudou são ignorados com aviso. Repetir a reparação não cria livros nem substitui campos já preenchidos.

## Editoras e cidade padrão

O menu **Editoras** permite buscar, cadastrar e editar editoras, com uma cidade padrão e a quantidade de títulos vinculados. O cadastro é privado por usuário. Nomes iguais (ignorando maiúsculas/minúsculas) são reutilizados ao cadastrar livros; nomes alternativos não são fundidos automaticamente.

Na ficha do livro, escolha uma sugestão no campo **Editora** ou digite um nome novo. Selecionar uma editora preenche sua cidade padrão somente quando a cidade de publicação está vazia. A cidade permanece editável e salva na própria edição; modificar a cidade padrão nunca altera as cidades dos livros anteriores. A referência ABNT continua usando a cidade do livro.

As editoras existentes foram aproveitadas. A migração define a cidade padrão quando os livros vinculados têm uma única cidade conhecida; com cidades diferentes, deixa o padrão vazio para revisão.

## Detalhes e referência ABNT salva

Clicar no título abre a ficha de leitura: metadados, capa ampliável, exemplares/localizações, valores, PDFs e referência ABNT. **Editar** abre o formulário; **Salvar cadastro** retorna aos detalhes. **Cancelar edição e voltar aos detalhes** recarrega os dados salvos.

A referência fica no campo de texto `abnt_reference` do livro/artigo e pode ser revisada manualmente. **Gerar novamente** substitui o conteúdo do campo usando os dados atuais do formulário, incluindo alterações ainda não salvas. **Salvar cadastro** persiste o texto com os demais campos. Alterar metadados não recalcula automaticamente uma referência existente. Novos cadastros geram a referência inicial ao salvar se o campo estiver vazio. A ficha exibe o texto gravado e permite copiá-lo.
