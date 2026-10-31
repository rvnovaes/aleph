# Importação de repositório pessoal de PDFs

O inventário contém caminhos privados e trechos dos documentos. Guardá-lo em `backups/`
(ignorado no Git), nunca em documentação pública.

1. `python3 scripts/scan-pdf-repository.py /caminho/do/repositorio backups/inventory.jsonl`
2. Transferir PDFs preservando caminhos relativos e o inventário para área privada no servidor.
3. Executar `python manage.py import_pdf_repository INVENTARIO RAIZ --username roberto --report RELATORIO --enrich`
   no ambiente Django com acesso à mídia e ao banco. O comando também pode ser montado
   temporariamente em `/app/catalog/management/commands/import_pdf_repository.py` em um
   container administrativo da mesma imagem de produção, sem interromper a aplicação.

O importador valida SHA-256 e leitura do PDF, ignora cópias binárias e aceita repetição
sem recriar registros importados. Preserva o PDF integral e registra origem e extração.
Não cria exemplar físico. Todos os registros afetados ficam pendentes de revisão.

Um único ISBN/DOI extraído habilita consulta pelos conectores existentes. A resposta
externa é preservada como proposta; edição e identificador não são confirmados por
semelhança de título. Metadados complementares exigem similaridade mínima de título.
Não há união automática com o acervo físico por título ou ISBN sugerido.

PDFs protegidos por senha, inválidos ou indisponíveis ficam no relatório de erros.
Arquivos digitalizados sem texto recebem título/autoria provisórios a partir do nome
quando os metadados internos não ajudam. Não se infere autoria a partir de referências
citadas no texto. EPUBs e demais formatos não são importados por este comando.

Esta rotina administrativa não usa o limite de upload web de 100 MB; mantém o arquivo
original. Realizar backup antes e depois do lote e conferir hashes e permissões da mídia.
