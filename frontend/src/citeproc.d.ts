declare module "citeproc" {
  const CSL: {
    Engine: new (
      system: {
        retrieveLocale: (lang: string) => string;
        retrieveItem: (id: string) => unknown;
      },
      style: string,
      language: string,
    ) => {
      updateItems(ids: string[]): void;
      makeBibliography(): [unknown, string[]];
      setOutputFormat(format: string): void;
    };
  };
  export default CSL;
}
