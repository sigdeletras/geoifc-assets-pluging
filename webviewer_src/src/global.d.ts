export {};

declare global {
  interface Window {
    GeoIfcViewer: {
      openReference(payload: {
        kind?: string;
        source?: string;
        dataBase64?: string;
      }): Promise<void>;
    };
  }
}
