/// <reference types="vite/client" />

interface ImportMetaEnv {
  /** Filename of the dataset CSV served from /public (see .env). */
  readonly VITE_DATASET_FILE?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}
